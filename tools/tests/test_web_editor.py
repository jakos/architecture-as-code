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

import submit
import web_editor

PASSWORD = "s3cret"
MODEL_PATH = "trial/likec4/shop"


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

    def __init__(self, repo: Path, submit_fn):
        page = repo / "page.html"
        page.write_text('<iframe src="__RENDER_URL__"></iframe>')
        self.editor = web_editor.Editor(
            repo, MODEL_PATH, "http://127.0.0.1:8095", run=fake_run, submit_fn=submit_fn, page=page
        )
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

    svc = Service(model_dir.parents[2], fake_submit)
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
    editor = web_editor.Editor(model_dir.parents[2], MODEL_PATH, "http://x")
    with pytest.raises(ValueError, match="PASSWORD"):
        web_editor.make_server(editor, "", "127.0.0.1", 0)


def test_main_exits_1_without_password(model_dir, monkeypatch, capsys):
    monkeypatch.delenv("PASSWORD", raising=False)
    argv = ["--repo", str(model_dir.parents[2]), "--path", MODEL_PATH, "--render-url", "http://x"]
    assert web_editor.main(argv) == 1
    assert "PASSWORD" in capsys.readouterr().err


def test_submit_endpoint_calls_submit_with_likec4_and_model_path(service, model_dir):
    status, data = service.call("POST", "/api/submit", {"message": "add notifications"})
    assert status == 200
    assert json.loads(data)["ok"] is True
    assert "pushed model/ada" in json.loads(data)["output"]
    assert service.calls == [("likec4", MODEL_PATH, model_dir.parents[2], "add notifications")]


def test_submit_endpoint_reports_submit_error(model_dir):
    def refuse(*args):
        raise submit.SubmitError("refusing to submit from 'main'")

    svc = Service(model_dir.parents[2], refuse)
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
    assert {cwd for _, cwd in seen} == {service.editor.model_dir}


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
