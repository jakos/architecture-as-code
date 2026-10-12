import base64
import http.client
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import model_source
import submit
import web_editor

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PASSWORD = "s3cret"
MODEL_PATH = "examples/shop"


def basic(password: str = PASSWORD) -> str:
    return "Basic " + base64.b64encode(f"user:{password}".encode()).decode()


@pytest.fixture
def model_dir(tmp_path):
    root = tmp_path / "clone" / MODEL_PATH
    root.mkdir(parents=True)
    (root / "model.c4").write_text("model {}\n")
    (root / "notes.md").write_text("not a model\n")
    (root / "views").mkdir()
    (root / "views" / "v.c4").write_text("views {}\n")
    return root


def fake_run(cmd, **kwargs):
    return subprocess.CompletedProcess(cmd, 0, "ok\n", "")


class Service:
    """A real server on an ephemeral port with injected runner and submit."""

    def __init__(self, repo: Path, submit_fn, static: Path | None = None):
        page = repo / "page.html"
        page.write_text('<iframe src="__RENDER_URL__"></iframe>')
        self.source = model_source.LocalCloneSource(
            repo, MODEL_PATH, run=fake_run, submit_fn=submit_fn
        )
        self.editor = web_editor.Editor(
            self.source, "http://127.0.0.1:8095", run=fake_run, page=page, static=static
        )
        self.last_headers: dict[str, str] = {}
        self.server = web_editor.make_server(self.editor, PASSWORD, "127.0.0.1", 0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def request(self, method, url, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        payload = json.dumps(body) if body is not None else None
        conn.request(method, url, payload, headers or {})
        response = conn.getresponse()
        data = response.read()
        self.last_headers = {k.lower(): v for k, v in response.getheaders()}
        conn.close()
        return response.status, data

    def call(self, method, url, body=None, origin=True):
        headers = {"Authorization": basic(), "Content-Type": "application/json"}
        if origin:
            headers["Origin"] = f"http://127.0.0.1:{self.port}"
        return self.request(method, url, body, headers)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def service(model_dir):
    calls = []

    def fake_submit(*args):
        calls.append(args)
        print("pushed model/ada/2026-10-10-x to origin")

    svc = Service(model_dir.parents[1], fake_submit)
    svc.calls = calls
    yield svc
    svc.stop()


@pytest.mark.parametrize("rel", ["../outside.c4", "/etc/passwd.c4", "a/../../x.c4", "\\x.c4", ""])
def test_rejects_path_outside_model_dir(model_dir, rel):
    with pytest.raises(web_editor.RequestError) as err:
        web_editor.resolve_model_file(model_dir, rel)
    assert err.value.status == 400


def test_rejects_non_c4_suffix(model_dir):
    with pytest.raises(web_editor.RequestError) as err:
        web_editor.resolve_model_file(model_dir, "notes.md")
    assert err.value.status == 400


def test_rejects_symlink_escape(model_dir, tmp_path):
    secret = tmp_path / "secret.c4"
    secret.write_text("secret\n")
    try:
        os.symlink(secret, model_dir / "link.c4")
        os.symlink(tmp_path, model_dir / "linkdir", target_is_directory=True)
    except OSError, NotImplementedError:
        pytest.skip("symlinks are not available here")
    for rel in ("link.c4", "linkdir/secret.c4"):
        with pytest.raises(web_editor.RequestError) as err:
            web_editor.resolve_model_file(model_dir, rel)
        assert err.value.status == 400
    assert "link.c4" not in web_editor.list_model_files(model_dir)


def test_put_writes_file_atomically(service, model_dir):
    status, _ = service.call("PUT", "/api/file?path=model.c4", {"text": "model { a }\n"})
    assert status == 200
    assert (model_dir / "model.c4").read_text() == "model { a }\n"
    assert [p.name for p in model_dir.iterdir() if p.name.endswith(".tmp")] == []


def test_put_failure_leaves_original_intact(model_dir, monkeypatch):
    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(web_editor.os, "replace", boom)
    with pytest.raises(OSError):
        web_editor.write_atomic(model_dir / "model.c4", "new")
    assert (model_dir / "model.c4").read_text() == "model {}\n"
    assert [p.name for p in model_dir.iterdir() if p.name.endswith(".tmp")] == []


def test_list_files_returns_only_c4(service):
    status, data = service.call("GET", "/api/files")
    assert status == 200
    assert json.loads(data)["files"] == ["model.c4", "views/v.c4"]


def test_put_rejects_bad_path_over_http(service):
    status, _ = service.call("PUT", "/api/file?path=../x.c4", {"text": "x"})
    assert status == 400


def test_requires_basic_auth(service):
    status, _ = service.request("GET", "/api/files")
    assert status == 401


def test_rejects_wrong_password(service):
    status, _ = service.request("GET", "/api/files", headers={"Authorization": basic("nope")})
    assert status == 401


def test_serves_page_with_render_url(service):
    status, data = service.call("GET", "/")
    assert status == 200
    assert b'src="http://127.0.0.1:8095"' in data


def test_keep_alive_serves_two_requests_on_one_connection(service):
    conn = http.client.HTTPConnection("127.0.0.1", service.port, timeout=5)
    try:
        for _ in range(2):
            conn.request("GET", "/api/files", headers={"Authorization": basic()})
            response = conn.getresponse()
            assert response.status == 200
            assert response.version == 11
            response.read()
    finally:
        conn.close()


def test_rejects_cross_origin_post(service):
    status, _ = service.request(
        "POST",
        "/api/validate",
        "{}",
        {"Authorization": basic(), "Origin": "http://evil.example"},
    )
    assert status == 403
    status, _ = service.call("POST", "/api/validate", {}, origin=False)
    assert status == 403


def test_refuses_to_start_without_password(model_dir):
    source = model_source.LocalCloneSource(model_dir.parents[1], MODEL_PATH)
    editor = web_editor.Editor(source, "http://x")
    with pytest.raises(ValueError, match="PASSWORD"):
        web_editor.make_server(editor, "", "127.0.0.1", 0)


def test_main_exits_1_without_password(model_dir, monkeypatch, capsys):
    monkeypatch.delenv("PASSWORD", raising=False)
    argv = ["--repo", str(model_dir.parents[1]), "--path", MODEL_PATH, "--render-url", "http://x"]
    assert web_editor.main(argv) == 1
    assert "PASSWORD" in capsys.readouterr().err


def test_submit_endpoint_calls_submit_with_likec4_and_model_path(service, model_dir):
    status, data = service.call("POST", "/api/submit", {"message": "add notifications"})
    assert status == 200
    assert json.loads(data)["ok"] is True
    assert "pushed model/ada" in json.loads(data)["output"]
    assert service.calls == [("likec4", MODEL_PATH, model_dir.parents[1], "add notifications")]


def test_submit_endpoint_reports_submit_error(model_dir):
    def refuse(*args):
        raise submit.SubmitError("refusing to submit from 'main'")

    svc = Service(model_dir.parents[1], refuse)
    try:
        status, data = svc.call("POST", "/api/submit", {"message": "x"})
    finally:
        svc.stop()
    assert status == 422
    assert "refusing to submit from 'main'" in json.loads(data)["error"]


def test_validate_runs_validate_and_format_check_in_model_dir(service):
    seen = []

    def recording_run(cmd, **kwargs):
        seen.append((cmd, kwargs.get("cwd")))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    service.editor.run = recording_run
    status, data = service.call("POST", "/api/validate", {})
    assert status == 200 and json.loads(data)["ok"] is True
    assert [c for c, _ in seen] == [["likec4", "validate"], ["likec4", "format", "--check"]]
    assert {cwd for _, cwd in seen} == {service.source.workdir()}


@pytest.mark.parametrize(
    "header", [None, "", "Bearer x", "Basic !!!", "Basic " + "/w==", "Basic eA=="]
)
def test_password_matches_rejects_malformed_headers(header):
    assert web_editor.password_matches(header, PASSWORD) is False


def test_tool_output_has_no_ansi_colours(service):
    def coloured(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "\x1b[2m18:10\x1b[22m bad\n", "")

    service.editor.run = coloured
    _, data = service.call("POST", "/api/validate", {})
    assert json.loads(data)["results"][0]["output"] == "18:10 bad"


@pytest.fixture
def static_dir(tmp_path):
    root = tmp_path / "editor"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<html>editor</html>")
    (root / "assets" / "app-AbCd1234.js").write_text("export {}")
    (root / "assets" / "app-AbCd1234.css").write_text("body{}")
    (root / "assets" / "layout-AbCd1234.wasm").write_bytes(b"\x00asm\x01\x00\x00\x00")
    (root / "assets" / "font-AbCd1234.woff2").write_bytes(b"wOF2")
    (root / "assets" / "data-AbCd1234.json").write_text("{}")
    (root / "icon.svg").write_text("<svg/>")
    (tmp_path / "secret.txt").write_text("secret")
    return root


@pytest.fixture
def static_service(model_dir, static_dir):
    svc = Service(model_dir.parents[1], lambda *args: None, static=static_dir)
    yield svc
    svc.stop()


def test_static_serves_index_and_spa_fallback(static_service):
    status, data = static_service.call("GET", "/")
    assert status == 200 and data == b"<html>editor</html>"
    assert static_service.last_headers["cache-control"] == "no-store"
    # a route of the single-page app has no file: it gets index.html
    status, data = static_service.call("GET", "/w/model/index/")
    assert status == 200 and data == b"<html>editor</html>"
    # a missing asset is a 404, not an HTML page
    status, _ = static_service.call("GET", "/assets/missing-AbCd1234.js")
    assert status == 404
    # the textarea page is not served in static mode, and no --render-url is needed
    assert b"__RENDER_URL__" not in data


@pytest.mark.parametrize(
    "url",
    [
        "/../secret.txt",
        "/assets/../../secret.txt",
        "/%2e%2e/secret.txt",
        "/assets/%2e%2e/%2e%2e/secret.txt",
        "/..%5csecret.txt",
    ],
)
def test_static_rejects_traversal(static_service, url):
    status, data = static_service.call("GET", url)
    assert status == 400
    assert b"secret" not in data


def test_static_rejects_symlink_escape(static_service, static_dir, tmp_path):
    try:
        os.symlink(tmp_path / "secret.txt", static_dir / "link.txt")
    except OSError, NotImplementedError:
        pytest.skip("symlinks are not available here")
    status, data = static_service.call("GET", "/link.txt")
    assert status == 400
    assert b"secret" not in data


def test_static_requires_basic_auth(static_service):
    for url in ("/", "/assets/app-AbCd1234.js", "/w/model/index/", "/icon.svg"):
        status, data = static_service.request("GET", url)
        assert status == 401, url
        assert b"editor" not in data
        assert "basic" in static_service.last_headers["www-authenticate"].lower()
    status, _ = static_service.request("GET", "/", headers={"Authorization": basic("nope")})
    assert status == 401
    # a state-changing request still needs the Origin check, static mode or not
    status, _ = static_service.call("POST", "/api/validate", {}, origin=False)
    assert status == 403


def test_static_wasm_and_js_content_types(static_service):
    expected = {
        "/assets/app-AbCd1234.js": "text/javascript",
        "/assets/app-AbCd1234.css": "text/css",
        "/assets/layout-AbCd1234.wasm": "application/wasm",
        "/assets/font-AbCd1234.woff2": "font/woff2",
        "/assets/data-AbCd1234.json": "application/json",
        "/icon.svg": "image/svg+xml",
    }
    for url, content_type in expected.items():
        status, _ = static_service.call("GET", url)
        assert status == 200, url
        assert static_service.last_headers["content-type"].startswith(content_type), url
    static_service.call("GET", "/assets/app-AbCd1234.js")
    assert "immutable" in static_service.last_headers["cache-control"]
    static_service.call("GET", "/icon.svg")
    assert "immutable" not in static_service.last_headers["cache-control"]


def test_workspace_returns_all_c4_files(service):
    status, data = service.call("GET", "/api/workspace")
    assert status == 200
    body = json.loads(data)
    assert body["files"] == {"model.c4": "model {}\n", "views/v.c4": "views {}\n"}
    assert body["branch"] == "ok"  # the fake runner answers every git call with "ok"


def test_validate_parses_problems_from_cli_output(service):
    output = (FIXTURES / "likec4_validate_broken.txt").read_bytes().decode()
    fmt_output = (FIXTURES / "likec4_format_check_broken.txt").read_bytes().decode()
    outputs = iter([output, fmt_output])

    def broken(cmd, **kwargs):
        # the CLI saw the model directory as /data (a container mount)
        return subprocess.CompletedProcess(cmd, 1, next(outputs), "")

    service.editor.run = broken
    service.source.model_dir = Path("/data")
    status, data = service.call("POST", "/api/validate", {})
    assert status == 200
    body = json.loads(data)
    assert body["ok"] is False
    problems = body["problems"]
    by_file = {}
    for problem in problems:
        by_file.setdefault(problem["path"], []).append(problem)
    people = by_file["shared/people.c4"]
    assert [(p["line"], p["severity"]) for p in people if p["line"]] == [(19, "error")] * 3
    assert "Could not resolve reference to Referenceable named 'nope1'" in people[0]["message"]
    assert all(p["column"] is None for p in problems)  # the CLI prints no column
    orders = by_file["teams/orders/model.c4"]
    assert any("found `descriptionn`" in p["message"] for p in orders)
    assert all(p["line"] == 9 for p in orders)
    # the token list that follows "Expecting:" belongs to that message
    expecting = next(p for p in orders if p["message"].startswith("Expecting: one of"))
    assert "[Dot]" in expecting["message"]
    # format --check names the file that needs formatting
    assert {
        k: next(p for p in people if p["message"] == "needs formatting")[k]
        for k in ("path", "line")
    } == {"path": "shared/people.c4", "line": None}
    # no path in a problem is absolute or outside the model
    assert all(p["path"] is None or not p["path"].startswith("/") for p in problems)


def test_validate_keeps_unparsed_output_as_problem(service):
    weird = (
        "something the CLI never printed before\n"
        "21:21:02.335 ERROR likec4.c4:validate Invalid (1 files, 2 errors)\n"
        "21:21:02.335 ERROR likec4 Invalid /elsewhere/other.c4\n"
        "    Line 4: outside the model\n"
        "21:21:00.488 INFO likec4.lang layout wasm\n"
    )

    def run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, weird, "")

    service.editor.run = run
    status, data = service.call("POST", "/api/validate", {})
    problems = json.loads(data)["problems"]
    assert status == 200
    messages = [(p["path"], p["line"], p["message"]) for p in problems]
    assert (None, None, "something the CLI never printed before") in messages
    assert (None, None, "Invalid (1 files, 2 errors)") in messages
    assert (None, None, "/elsewhere/other.c4: Line 4: outside the model") in messages
    assert not any("layout wasm" in m[2] for m in messages)  # plain INFO log lines are not problems
    raw = json.loads(data)["results"][0]["output"]
    assert "something the CLI never printed before" in raw  # the raw output is kept too


def test_format_reports_changed_files(service, model_dir):
    def run(cmd, **kwargs):
        (model_dir / "views" / "v.c4").write_text("views {\n}\n")
        return subprocess.CompletedProcess(cmd, 0, "formatted\n", "")

    service.editor.run = run
    status, data = service.call("POST", "/api/format", {})
    body = json.loads(data)
    assert status == 200 and body["ok"] is True
    assert body["changed"] == ["views/v.c4"]
    # nothing to change: the list is empty
    service.editor.run = fake_run
    _, data = service.call("POST", "/api/format", {})
    assert json.loads(data)["changed"] == []


def test_submit_returns_skipped_files(model_dir):
    def fake_submit(*args):
        print("skipped (not committed): examples/shop/.likec4/x.likec4.snap")
        print("pushed model/ada/2026-10-11-x to origin")

    svc = Service(model_dir.parents[1], fake_submit)
    try:
        status, data = svc.call("POST", "/api/submit", {"message": "x"})
    finally:
        svc.stop()
    assert status == 200
    assert json.loads(data)["skipped"] == [".likec4/x.likec4.snap"]


def test_main_needs_render_url_or_static(model_dir, monkeypatch, capsys):
    monkeypatch.setenv("PASSWORD", PASSWORD)
    with pytest.raises(SystemExit) as err:
        web_editor.main(["--repo", str(model_dir.parents[1]), "--path", MODEL_PATH])
    assert err.value.code == 2
    assert "--render-url" in capsys.readouterr().err


class FakeSource:
    """A ModelSource with no git and no filesystem: the editor must work with only this."""

    def __init__(self):
        self.files = {"a.c4": "model {}\n", "b/c.c4": "views {}\n"}
        self.calls = []

    def branch(self):
        return "model/ada/2026-10-11-fake"

    def list_files(self):
        return sorted(self.files)

    def read(self, rel):
        self.calls.append(("read", rel))
        return self.files[rel]

    def write(self, rel, text):
        self.calls.append(("write", rel))
        self.files[rel] = text

    def changes(self):
        return [" M a.c4"]

    def workdir(self):
        return Path("/nonexistent/model")

    def submit(self, message):
        self.calls.append(("submit", message))
        return model_source.SubmitResult(output="pushed", skipped=["x.snap"])


def test_editor_uses_only_model_source(tmp_path):
    seen = []

    def run(cmd, **kwargs):
        seen.append((cmd, kwargs.get("cwd")))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    source = FakeSource()
    assert isinstance(source, model_source.ModelSource)
    editor = web_editor.Editor(source, run=run, static=tmp_path)
    assert editor.workspace() == {"branch": source.branch(), "files": source.files}
    editor.write_file("a.c4", "model { x }\n")
    assert editor.read_file("a.c4") == "model { x }\n"
    assert editor.status() == {"branch": source.branch(), "changes": [" M a.c4"]}
    assert editor.submit("msg") == {"ok": True, "output": "pushed", "skipped": ["x.snap"]}
    assert editor.format()["changed"] == []
    editor.validate()
    # CLI tools run in the directory the source names, and git is never called by the editor
    assert {cwd for _, cwd in seen} == {Path("/nonexistent/model")}
    assert all(cmd[0] == "likec4" for cmd, _ in seen)
    assert ("submit", "msg") in source.calls
    # over HTTP as well: the handler reaches the model only through the source
    server = web_editor.make_server(editor, PASSWORD, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
        conn.request("GET", "/api/files", headers={"Authorization": basic()})
        response = conn.getresponse()
        assert json.loads(response.read())["files"] == ["a.c4", "b/c.c4"]
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
