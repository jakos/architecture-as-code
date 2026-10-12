"""Browser editing service for a LikeC4 model in a clone (B1 editor PoC, local only).

Serves either the built model editor (`--static <dir>`: the LikeC4 playground with our patch
set, see docker/editor/model-editor) or the older single textarea page (text editor on the
left, the `likec4 start` diagram in an iframe on the right), plus a small JSON API on the
`.c4` files of the model. The model is reached only through a `ModelSource` (model_source.py);
`POST /api/submit` goes to `ModelSource.submit` (validate, commit the `.c4` files, send the
model/* branch to `origin`, print the PR command). It never runs `gh`.

Every request (static files included) needs HTTP Basic auth with the password from the
PASSWORD environment variable; every non-GET request needs an Origin header equal to the
page's own origin.

Stdlib only and no 3.14-only syntax: it runs on the Python 3 shipped in the images.
"""

import argparse
import base64
import hmac
import html
import json
import mimetypes
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, unquote, urlsplit

from model_source import (  # noqa: F401  (re-exported: the path guard lives in model_source)
    SUFFIX,
    LocalCloneSource,
    ModelSource,
    SourceError,
    list_model_files,
    resolve_model_file,
    write_atomic,
)

MAX_BODY = 1024 * 1024
HTML_NAME = "web_editor.html"
INDEX_NAME = "index.html"
RENDER_PLACEHOLDER = "__RENDER_URL__"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")  # likec4 colours its log lines
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".wasm": "application/wasm",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".txt": "text/plain; charset=utf-8",
}
IMMUTABLE = "public, max-age=31536000, immutable"  # hashed build output under assets/

# One line of likec4's log output, colours removed: "21:21:02.335 ERROR likec4 Invalid /data/a.c4".
LOG_RE = re.compile(r"^\d\d:\d\d:\d\d\.\d+ +(?P<level>[A-Z]+) +\S+ (?P<text>.*)$")
INVALID_RE = re.compile(
    r"^Invalid (?!\()(?P<path>.+)$"
)  # not the "Invalid (29 files, ...)" summary
LINE_RE = re.compile(r"^\s+Line (?P<line>\d+): (?P<message>.*)$")
NEEDS_FORMAT_RE = re.compile(r"^needs formatting (?P<path>.+)$")
SEVERITIES = {"ERROR": "error", "WARN": "warning", "WARNING": "warning"}

Runner = Callable[..., subprocess.CompletedProcess]

# A refusal that maps to an HTTP status and a message for the caller.
RequestError = SourceError


def plain(text: str) -> str:
    return ANSI_RE.sub("", text)


def _relative_to_workdir(raw: str, workdir: Path) -> str | None:
    """Model-relative POSIX path for a path printed by likec4, or None if it is elsewhere."""
    text = raw.strip().replace("\\", "/")
    for base in {workdir.as_posix().rstrip("/"), workdir.resolve().as_posix().rstrip("/")}:
        if text.startswith(base + "/"):
            return text[len(base) + 1 :]
    if text.startswith("/") or re.match(r"^[A-Za-z]:/", text):
        return None  # absolute, but not inside the model directory
    return text


def parse_problems(output: str, workdir: Path) -> list[dict]:
    """Turn `likec4 validate` / `format --check` output into problems for the editor.

    Known shapes (see tools/tests/fixtures): an `Invalid <file>` log line followed by indented
    `Line <n>: <message>` lines (the CLI prints no column), and `needs formatting <file>`.
    Informational log lines are recognised and skipped (the raw output stays in `results`).
    Anything else is kept as a problem without a path: nothing is dropped silently.
    """
    problems: list[dict] = []
    seen: set[tuple] = set()
    context: tuple[str | None, str, str] | None = None  # path, raw path, severity
    last: dict | None = None

    def add(path, line, severity, message) -> None:
        nonlocal last
        key = (path, line, message)
        if key in seen:
            last = {"message": ""}  # a repeat: its continuation lines go nowhere
            return
        seen.add(key)
        last = {
            "path": path,
            "line": line,
            "column": None,
            "severity": severity,
            "message": message,
        }
        problems.append(last)

    for raw_line in plain(output).splitlines():
        if not raw_line.strip():
            continue
        log = LOG_RE.match(raw_line)
        if log:
            context = None
            last = None
            text = log.group("text")
            severity = SEVERITIES.get(log.group("level"))
            invalid = INVALID_RE.match(text)
            needs_format = NEEDS_FORMAT_RE.match(text)
            if invalid:
                raw_path = invalid.group("path")
                context = (
                    _relative_to_workdir(raw_path, workdir),
                    raw_path,
                    severity or "error",
                )
            elif needs_format:
                path = _relative_to_workdir(needs_format.group("path"), workdir)
                add(path, None, "warning", "needs formatting")
            elif severity:
                add(None, None, severity, text)
            continue
        line = LINE_RE.match(raw_line)
        if line and context is not None:
            path, raw_path, severity = context
            number = int(line.group("line"))
            if path is None:
                add(None, None, severity, f"{raw_path}: Line {number}: {line.group('message')}")
            else:
                add(path, number, severity, line.group("message"))
        elif last is not None:
            last["message"] += "\n" + raw_line.strip()  # continuation of the previous message
        else:
            add(None, None, "error", raw_line.strip())
    return problems


class Editor:
    """What the API does, kept apart from HTTP so the handler stays thin."""

    def __init__(
        self,
        source: ModelSource,
        render_url: str = "",
        run: Runner = subprocess.run,
        page: Path | None = None,
        static: Path | None = None,
    ) -> None:
        self.source = source
        self.render_url = render_url
        self.run = run
        self.page = page or Path(__file__).with_name(HTML_NAME)
        self.static = static

    def index(self) -> str:
        text = self.page.read_text(encoding="utf-8")
        return text.replace(RENDER_PLACEHOLDER, html.escape(self.render_url, quote=True))

    def static_file(self, route: str) -> tuple[bytes, str, str]:
        """Body, content type and Cache-Control of a built-editor file, or index.html for the
        single-page app's own routes. Raises a 400 for a traversal attempt and a 404 for a
        missing file that looks like an asset."""
        if self.static is None:
            raise RequestError(HTTPStatus.NOT_FOUND, "not found")
        rel = unquote(route).lstrip("/")
        parts = PurePosixPath(rel).parts
        if "\x00" in rel or "\\" in rel or ".." in parts:
            raise RequestError(HTTPStatus.BAD_REQUEST, "path must stay in the editor files")
        root = self.static.resolve()
        target = (root / rel).resolve() if rel else root / INDEX_NAME
        if root not in target.parents:
            raise RequestError(HTTPStatus.BAD_REQUEST, "path resolves outside the editor files")
        if not target.is_file():
            if parts and "." in parts[-1]:
                raise RequestError(HTTPStatus.NOT_FOUND, "not found")
            target = root / INDEX_NAME  # route of the single-page app
            if not target.is_file():
                raise RequestError(HTTPStatus.NOT_FOUND, "the editor build is missing")
        content_type = (
            CONTENT_TYPES.get(target.suffix.lower())
            or mimetypes.guess_type(target.name)[0]
            or "application/octet-stream"
        )
        if target.name == INDEX_NAME:
            cache = "no-store"
        elif "assets" in target.relative_to(root).parts[:-1]:
            cache = IMMUTABLE
        else:
            cache = "no-cache"
        return target.read_bytes(), content_type, cache

    def read_file(self, rel: str) -> str:
        return self.source.read(rel)

    def write_file(self, rel: str, text: str) -> None:
        self.source.write(rel, text)

    def workspace(self) -> dict:
        """Every `.c4` file in one response: what the in-browser language server needs."""
        return {"branch": self.source.branch(), "files": self._snapshot()}

    def _snapshot(self) -> dict[str, str]:
        return {rel: self.source.read(rel) for rel in self.source.list_files()}

    def _tool(self, cmd: list[str]) -> dict:
        proc = self.run(cmd, cwd=self.source.workdir(), capture_output=True, text=True, check=False)
        output = (proc.stdout or "") + (proc.stderr or "")
        return {
            "command": shlex.join(cmd),
            "exit": proc.returncode,
            "output": plain(output).strip(),
        }

    def validate(self) -> dict:
        results = [self._tool(["likec4", "validate"]), self._tool(["likec4", "format", "--check"])]
        workdir = self.source.workdir()
        problems: list[dict] = []
        for result in results:
            for problem in parse_problems(result["output"], workdir):
                if problem not in problems:
                    problems.append(problem)
        return {
            "ok": all(r["exit"] == 0 for r in results),
            "results": results,
            "problems": problems,
        }

    def format(self) -> dict:
        before = self._snapshot()
        result = self._tool(["likec4", "format"])
        after = self._snapshot()
        changed = [rel for rel, text in after.items() if before.get(rel) != text]
        return {"ok": result["exit"] == 0, "results": [result], "changed": changed}

    def status(self) -> dict:
        return {"branch": self.source.branch(), "changes": self.source.changes()}

    def submit(self, message: str) -> dict:
        result = self.source.submit(message)
        return {"ok": True, "output": result.output, "skipped": list(result.skipped)}


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
        # Keep-alive: close-after-response truncated/reset large assets over the Podman
        # port forward from the Windows host. Every response sends Content-Length.
        protocol_version = "HTTP/1.1"
        timeout = 60  # idle keep-alive connections must not hold a thread forever

        def log_message(self, format: str, *args: object) -> None:
            # Method, path without query and status only: never headers or bodies.
            first = str(args[0]).split(" ") if args else []
            line = " ".join(first[:2]).split("?")[0]
            sys.stderr.write(f"{line} {' '.join(str(a) for a in args[1:2])}\n")

        def _send(
            self, status: int, body: bytes, content_type: str, extra=None, cache: str = "no-store"
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", cache)
            self.send_header("X-Content-Type-Options", "nosniff")
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
            if method == "GET" and not route.startswith("/api/"):
                if editor.static is not None:
                    body, content_type, cache = editor.static_file(route)
                    self._send(200, body, content_type, cache=cache)
                elif route == "/":
                    self._send(200, editor.index().encode(), "text/html; charset=utf-8")
                else:
                    raise RequestError(HTTPStatus.NOT_FOUND, "not found")
            elif method == "GET" and route == "/api/files":
                self._json(200, {"files": editor.source.list_files()})
            elif method == "GET" and route == "/api/workspace":
                self._json(200, editor.workspace())
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
                message = message.strip() or f"model: update {editor.source.workdir().name}"
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
    parser.add_argument("--render-url", help="URL of the likec4 dev server (textarea page only)")
    parser.add_argument("--static", help="directory of the built model editor to serve")
    args = parser.parse_args(argv)
    if not args.static and not args.render_url:
        parser.error("--render-url is required unless --static is given")

    password = os.environ.get("PASSWORD", "")
    source = LocalCloneSource(Path(args.repo).resolve(), args.path)
    static = Path(args.static).resolve() if args.static else None
    editor = Editor(source, args.render_url or "", static=static)
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
