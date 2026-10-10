"""Browser editing service for a LikeC4 model in a clone (B1 editor PoC, local only).

Serves one page (text editor on the left, the `likec4 start` diagram in an iframe on the
right) and a small JSON API that reads and writes the `.c4` files of the model directory in
the clone. `POST /api/submit` calls `submit.submit` (validate, commit the model directory,
send the model/* branch to `origin`, print the PR command). It never runs `gh`.

Every request needs HTTP Basic auth with the password from the PASSWORD environment
variable; every non-GET request needs an Origin header equal to the page's own origin.

Stdlib only and no 3.14-only syntax: it runs on the Python 3 shipped in the images.
"""

import argparse
import base64
import contextlib
import hmac
import html
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
from collections.abc import Callable, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import submit

MAX_BODY = 1024 * 1024
SUFFIX = ".c4"
HTML_NAME = "web_editor.html"
RENDER_PLACEHOLDER = "__RENDER_URL__"
ANSI_RE = re.compile(r"\[[0-9;]*m")  # likec4 colours its log lines

Runner = Callable[..., subprocess.CompletedProcess]
SubmitFn = Callable[..., None]


class RequestError(Exception):
    """A refusal that maps to an HTTP status and a message for the caller."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def plain(text: str) -> str:
    return ANSI_RE.sub("", text)


def resolve_model_file(model_dir: Path, rel: str) -> Path:
    """Map a relative `.c4` path to a file inside model_dir, or raise a 400."""
    if not rel or "\x00" in rel:
        raise RequestError(HTTPStatus.BAD_REQUEST, "path is missing")
    candidate = Path(rel)
    if candidate.is_absolute() or rel.startswith(("/", "\\")) or ".." in candidate.parts:
        raise RequestError(HTTPStatus.BAD_REQUEST, "path must be relative and stay in the model")
    if candidate.suffix != SUFFIX:
        raise RequestError(HTTPStatus.BAD_REQUEST, f"only {SUFFIX} files can be edited")
    root = model_dir.resolve()
    target = (root / candidate).resolve()  # follows symlinks, so an escaping link is caught
    if root != target and root not in target.parents:
        raise RequestError(HTTPStatus.BAD_REQUEST, "path resolves outside the model directory")
    return target


def list_model_files(model_dir: Path) -> list[str]:
    """Relative POSIX paths of the `.c4` files under model_dir that really live inside it."""
    root = model_dir.resolve()
    found = []
    for item in sorted(root.rglob(f"*{SUFFIX}")):
        if item.is_file() and (root in item.resolve().parents):
            found.append(item.relative_to(root).as_posix())
    return found


def write_atomic(target: Path, text: str) -> None:
    """Write next to the target and rename over it, so readers never see half a file."""
    fd, tmp_name = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.replace(tmp_name, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise


class Editor:
    """What the API does, kept apart from HTTP so the handler stays thin."""

    def __init__(
        self,
        repo: Path,
        path: str,
        render_url: str,
        run: Runner = subprocess.run,
        submit_fn: SubmitFn = submit.submit,
        page: Path | None = None,
    ) -> None:
        self.repo = repo
        self.path = path
        self.model_dir = repo / path
        self.render_url = render_url
        self.run = run
        self.submit_fn = submit_fn
        self.page = page or Path(__file__).with_name(HTML_NAME)
        self.lock = threading.Lock()  # submit prints to stdout; one command at a time

    def index(self) -> str:
        text = self.page.read_text(encoding="utf-8")
        return text.replace(RENDER_PLACEHOLDER, html.escape(self.render_url, quote=True))

    def read_file(self, rel: str) -> str:
        target = resolve_model_file(self.model_dir, rel)
        if not target.is_file():
            raise RequestError(HTTPStatus.NOT_FOUND, f"{rel} does not exist")
        return target.read_text(encoding="utf-8")

    def write_file(self, rel: str, text: str) -> None:
        target = resolve_model_file(self.model_dir, rel)
        if not target.parent.is_dir():
            raise RequestError(HTTPStatus.BAD_REQUEST, "the directory of that file does not exist")
        write_atomic(target, text)

    def _tool(self, cmd: list[str]) -> dict:
        proc = self.run(cmd, cwd=self.model_dir, capture_output=True, text=True, check=False)
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "command": shlex.join(cmd),
            "exit": proc.returncode,
            "output": plain(output).strip(),
        }

    def validate(self) -> dict:
        results = [self._tool(["likec4", "validate"]), self._tool(["likec4", "format", "--check"])]
        return {"ok": all(r["exit"] == 0 for r in results), "results": results}

    def format(self) -> dict:
        result = self._tool(["likec4", "format"])
        return {"ok": result["exit"] == 0, "results": [result]}

    def status(self) -> dict:
        def git(*args: str) -> str:
            proc = self.run(
                ["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=False
            )
            return (proc.stdout or "").strip()

        return {"branch": git("branch", "--show-current"), "changes": git(*self._porcelain())}

    def _porcelain(self) -> tuple[str, ...]:
        return ("status", "--porcelain", "--", self.path)

    def submit(self, message: str) -> dict:
        buffer = io.StringIO()
        with self.lock, contextlib.redirect_stdout(buffer):
            try:
                self.submit_fn("likec4", self.path, self.repo, message)
            except submit.SubmitError as err:
                raise RequestError(HTTPStatus.UNPROCESSABLE_ENTITY, plain(str(err))) from err
        return {"ok": True, "output": buffer.getvalue().strip()}


def password_matches(header: str | None, password: str) -> bool:
    """Constant-time check of an `Authorization: Basic ...` header against the password."""
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
    except ValueError:  # binascii.Error and UnicodeDecodeError are both ValueErrors
        return False
    _user, sep, given = decoded.partition(":")
    return bool(sep) and hmac.compare_digest(given.encode(), password.encode())


def make_handler(editor: Editor, password: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "web-editor"

        def log_message(self, format: str, *args: object) -> None:
            # Method, path without query and status only: never headers or bodies.
            first = str(args[0]).split(" ") if args else []
            line = " ".join(first[:2]).split("?")[0]
            sys.stderr.write(f"{line} {' '.join(str(a) for a in args[1:2])}\n")

        def _send(self, status: int, body: bytes, content_type: str, extra=None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for key, value in (extra or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: object) -> None:
            self._send(status, json.dumps(payload).encode(), "application/json; charset=utf-8")

        def _guard(self, write: bool) -> None:
            if not password_matches(self.headers.get("Authorization"), password):
                raise RequestError(HTTPStatus.UNAUTHORIZED, "authentication required")
            if write:
                own = f"http://{self.headers.get('Host', '')}"
                if self.headers.get("Origin") != own:
                    raise RequestError(HTTPStatus.FORBIDDEN, "cross-origin request refused")

        def _read_raw(self) -> bytes:
            """Read the whole request body up front, so an early refusal never leaves it unread
            (an unread body makes some clients see a connection reset instead of the answer)."""
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length < 0 or length > MAX_BODY:
                self.close_connection = True
                raise RequestError(HTTPStatus.BAD_REQUEST, "body missing or too large")
            return self.rfile.read(length) if length else b""

        def _body(self) -> dict:
            try:
                data = json.loads(self._raw or b"{}")
            except json.JSONDecodeError as err:
                raise RequestError(HTTPStatus.BAD_REQUEST, "body is not JSON") from err
            if not isinstance(data, dict):
                raise RequestError(HTTPStatus.BAD_REQUEST, "body must be a JSON object")
            return data

        def _query_path(self) -> str:
            return parse_qs(urlsplit(self.path).query).get("path", [""])[0]

        def _handle(self, method: str) -> None:
            route = urlsplit(self.path).path
            self._raw = b""
            try:
                if method != "GET":
                    self._raw = self._read_raw()
                self._guard(write=method != "GET")
                self._route(method, route)
            except RequestError as err:
                headers = None
                if err.status == HTTPStatus.UNAUTHORIZED:
                    headers = {"WWW-Authenticate": 'Basic realm="model editor"'}
                self._send(
                    err.status,
                    json.dumps({"error": err.message}).encode(),
                    "application/json; charset=utf-8",
                    headers,
                )

        def _route(self, method: str, route: str) -> None:
            if method == "GET" and route == "/":
                self._send(200, editor.index().encode(), "text/html; charset=utf-8")
            elif method == "GET" and route == "/api/files":
                self._json(200, {"files": list_model_files(editor.model_dir)})
            elif method == "GET" and route == "/api/file":
                self._json(200, {"text": editor.read_file(self._query_path())})
            elif method == "PUT" and route == "/api/file":
                text = self._body().get("text")
                if not isinstance(text, str):
                    raise RequestError(HTTPStatus.BAD_REQUEST, "'text' must be a string")
                editor.write_file(self._query_path(), text)
                self._json(200, {"ok": True})
            elif method == "GET" and route == "/api/status":
                self._json(200, editor.status())
            elif method == "POST" and route == "/api/validate":
                self._json(200, editor.validate())
            elif method == "POST" and route == "/api/format":
                self._json(200, editor.format())
            elif method == "POST" and route == "/api/submit":
                message = self._body().get("message", "")
                if not isinstance(message, str):
                    raise RequestError(HTTPStatus.BAD_REQUEST, "'message' must be a string")
                message = message.strip() or f"model: update {editor.path}"
                self._json(200, editor.submit(message))
            else:
                raise RequestError(HTTPStatus.NOT_FOUND, "not found")

        def do_GET(self) -> None:
            self._handle("GET")

        def do_PUT(self) -> None:
            self._handle("PUT")

        def do_POST(self) -> None:
            self._handle("POST")

    return Handler


def make_server(
    editor: Editor, password: str, host: str = "0.0.0.0", port: int = 8080
) -> ThreadingHTTPServer:
    """Build the HTTP server; refuses an empty password."""
    if not password:
        raise ValueError("PASSWORD is not set: refusing to start without authentication")
    return ThreadingHTTPServer((host, port), make_handler(editor, password))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="clone that holds the model")
    parser.add_argument("--path", required=True, help="model directory, relative to the repo")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--render-url", required=True, help="URL of the likec4 dev server")
    args = parser.parse_args(argv)

    password = os.environ.get("PASSWORD", "")
    editor = Editor(Path(args.repo).resolve(), args.path, args.render_url)
    try:
        server = make_server(editor, password, port=args.port)
    except ValueError as err:
        print(f"web_editor: {err}", file=sys.stderr)
        return 1
    print(f"web_editor: serving {args.path} on port {args.port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
