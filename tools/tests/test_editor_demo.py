import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import editor_demo
from editor_demo import check_bundle
from validate_models import CONFIG_NAME
from viewer import ViewerError

PROJECT = "examples/shop"
BASE = "/architecture-as-code/editor/"
IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
# CRLF and non-ASCII: the workspace must hold the committed text byte for byte.
MODEL_TEXT = "model { // zażółć\r\n}\r\n"
INDEX = (
    "<!doctype html><html><head>"
    f'<script type="module" src="{BASE}assets/app.js"></script>'
    f'<link rel="stylesheet" href="{BASE}assets/app.css"></head><body></body></html>'
)


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *IDENTITY, *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "core.autocrlf", "false")
    (path / ".gitignore").write_text("build/\n")
    project = path / PROJECT
    (project / "views").mkdir(parents=True)
    (project / CONFIG_NAME).write_text("{}")
    (project / "model.c4").write_bytes(MODEL_TEXT.encode())
    (project / "views" / "index.c4").write_bytes(b"views {}\n")
    (project / "notes.md").write_text("not a model file\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "model")
    return path


@pytest.fixture
def app(tmp_path):
    path = tmp_path / "app"
    (path / "assets").mkdir(parents=True)
    (path / "index.html").write_text(INDEX)
    (path / "assets" / "app.js").write_text("console.log('hi')")
    (path / "assets" / "app.css").write_text("body{}")
    return path


def run_assemble(repo: Path, app: Path, *extra: str) -> int:
    return editor_demo.main(
        [
            "assemble",
            "--base",
            BASE,
            "--project",
            PROJECT,
            "--app",
            str(app),
            "--repo",
            str(repo),
            *extra,
        ]
    )


def test_workspace_holds_the_committed_c4_files_at_the_ref(repo, app):
    git(repo, "branch", "old")
    # Later commits must not show up in the workspace of the older ref.
    (repo / PROJECT / "model.c4").write_text("changed later")
    (repo / PROJECT / "later.c4").write_text("added later")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "later")

    assert run_assemble(repo, app, "--ref", "old") == 0
    data = json.loads((repo / "build/pages/editor/workspace.json").read_text(encoding="utf-8"))
    assert data == {"files": {"model.c4": MODEL_TEXT, "views/index.c4": "views {}\n"}}


def test_workspace_ignores_working_tree_and_untracked_files(repo, app):
    (repo / PROJECT / "model.c4").write_text("dirty")
    (repo / PROJECT / "untracked.c4").write_text("untracked")
    assert run_assemble(repo, app, "--ref", "main") == 0
    data = json.loads((repo / "build/pages/editor/workspace.json").read_text(encoding="utf-8"))
    assert sorted(data["files"]) == ["model.c4", "views/index.c4"]
    assert data["files"]["model.c4"] == MODEL_TEXT
    assert not (repo / "build/pages/editor/notes.md").exists()


def test_assemble_copies_the_app_next_to_workspace_json_and_replaces_an_older_out(repo, app):
    out = repo / "build/pages/editor"
    out.mkdir(parents=True)
    (out / "stale.txt").write_text("old")
    assert run_assemble(repo, app) == 0
    assert (out / "index.html").read_text() == INDEX
    assert (out / "assets" / "app.js").is_file()
    assert (out / "workspace.json").is_file()
    assert not (out / "stale.txt").exists()
    # nothing is left over next to it, and the source app is untouched
    assert [p.name for p in out.parent.iterdir()] == ["editor"]
    assert not (app / "workspace.json").exists()


def test_assemble_refuses_an_out_outside_build(repo, app, tmp_path, capsys):
    outside = tmp_path / "elsewhere"
    assert run_assemble(repo, app, "--out", str(outside)) == 1
    assert "must be inside" in capsys.readouterr().err
    assert not outside.exists()
    assert (
        run_assemble(repo, app, "--out", str(repo / "build")) == 1
    )  # build itself: not strictly inside


def test_missing_app_fails_and_names_the_recipe(repo, tmp_path, capsys):
    assert run_assemble(repo, tmp_path / "nope") == 1
    assert "just editor-demo-app" in capsys.readouterr().err
    assert not (repo / "build").exists()


def test_missing_app_with_optional_skips_and_writes_nothing(repo, tmp_path, capsys):
    assert run_assemble(repo, tmp_path / "nope", "--optional") == 0
    assert "skipped" in capsys.readouterr().out
    assert not (repo / "build").exists()


def test_assemble_rejects_an_unsafe_base(repo, app, capsys):
    code = editor_demo.main(
        ["assemble", "--base", "no-slash", "--app", str(app), "--repo", str(repo)]
    )
    assert code == 1
    assert "invalid base" in capsys.readouterr().err


def test_assemble_unknown_ref_or_project_fails(repo, app, capsys):
    assert run_assemble(repo, app, "--ref", "nope") == 1
    assert "unknown ref" in capsys.readouterr().err
    code = editor_demo.main(
        ["assemble", "--base", BASE, "--project", "examples/none", "--app", str(app),
         "--repo", str(repo)]
    )  # fmt: skip
    assert code == 1
    assert not (repo / "build/pages/editor").exists()


def test_check_bundle_accepts_a_clean_app(app):
    check_bundle(app, BASE)


def test_check_bundle_rejects_a_missing_index(app):
    (app / "index.html").unlink()
    with pytest.raises(ViewerError, match=r"index\.html"):
        check_bundle(app, BASE)


@pytest.mark.parametrize(
    "url",
    [
        "/assets/app.js",  # root path: outside the base
        "/architecture-as-code/assets/app.js",  # the viewer's directory
        "https://cdn.example.com/x.js",
        "//cdn.example.com/x.js",
        "assets/app.js",  # relative
    ],
)
def test_check_bundle_rejects_an_asset_url_outside_the_base(app, url):
    (app / "index.html").write_text(f'<script src="{url}"></script>')
    with pytest.raises(ViewerError, match="outside"):
        check_bundle(app, BASE)


def test_check_bundle_rejects_a_python_file(app):
    (app / "server.py").write_text("print('server')")
    with pytest.raises(ViewerError, match=r"Python file: server\.py"):
        check_bundle(app, BASE)


@pytest.mark.parametrize("api", ["/api/submit", "/api/workspace", "/api/file", "/api/validate"])
def test_check_bundle_rejects_a_file_with_a_server_api_path(app, api):
    (app / "assets" / "app.js").write_text(f"fetch('{api}')")
    with pytest.raises(ViewerError, match=r"assets/app\.js"):
        check_bundle(app, BASE)


class FakeEngine:
    """Records engine commands; `create` prints a container id, `cp` fills the destination."""

    def __init__(self, fail_cp: bool = False, fail_build: bool = False, with_api: bool = False):
        self.calls: list[list[str]] = []
        self.fail_cp = fail_cp
        self.fail_build = fail_build
        self.with_api = with_api

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        verb = cmd[1]
        if verb == "build":
            return subprocess.CompletedProcess(cmd, 1 if self.fail_build else 0)
        if verb == "create":
            return subprocess.CompletedProcess(cmd, 0, stdout=b"abc123\n")
        if verb == "cp":
            if self.fail_cp:
                return subprocess.CompletedProcess(cmd, 1)
            dest = Path(cmd[3])
            (dest / "index.html").write_text(INDEX)
            (dest / "app.js").write_text("fetch('/api/submit')" if self.with_api else "ok")
            return subprocess.CompletedProcess(cmd, 0)
        return subprocess.CompletedProcess(cmd, 0)


def run_app(repo: Path, engine: FakeEngine, *extra: str) -> int:
    return editor_demo.main(
        ["app", "--base", BASE, "--engine", "eng", "--repo", str(repo), *extra], run=engine
    )


def test_app_builds_the_demo_target_with_the_base_and_extracts_it(repo):
    engine = FakeEngine()
    assert run_app(repo, engine) == 0
    build, create, cp, rm = engine.calls
    assert build == [
        "eng",
        "build",
        "-f",
        "docker/editor/model-editor/Containerfile",
        "--target",
        "demo",
        "--build-arg",
        f"DEMO_BASE={BASE}",
        "-t",
        "localhost/aac-editor-demo:v1.59.4",
        ".",
    ]
    assert create[:3] == ["eng", "create", "localhost/aac-editor-demo:v1.59.4"]
    assert cp[:3] == ["eng", "cp", "abc123:/demo/."]
    assert rm == ["eng", "rm", "-f", "abc123"]
    out = repo / "build/editor-demo-app"
    assert (out / "index.html").read_text() == INDEX
    assert [p.name for p in out.parent.iterdir()] == ["editor-demo-app"]


def test_app_removes_the_container_when_cp_fails_and_keeps_the_old_app(repo, capsys):
    out = repo / "build/editor-demo-app"
    out.mkdir(parents=True)
    (out / "index.html").write_text("previous")
    engine = FakeEngine(fail_cp=True)
    assert run_app(repo, engine) == 1
    assert ["eng", "rm", "-f", "abc123"] in engine.calls
    assert "cp failed" in capsys.readouterr().err
    assert (out / "index.html").read_text() == "previous"
    assert [p.name for p in out.parent.iterdir()] == ["editor-demo-app"]


def test_app_refuses_a_bundle_with_server_api_and_keeps_the_old_app(repo, capsys):
    out = repo / "build/editor-demo-app"
    out.mkdir(parents=True)
    (out / "index.html").write_text("previous")
    assert run_app(repo, FakeEngine(with_api=True)) == 1
    assert "/api/submit" in capsys.readouterr().err
    assert (out / "index.html").read_text() == "previous"


def test_app_fails_when_the_image_build_fails(repo):
    engine = FakeEngine(fail_build=True)
    assert run_app(repo, engine) == 1
    assert [c[1] for c in engine.calls] == ["build"]  # no container was created


def test_app_refuses_an_out_outside_build(repo, tmp_path, capsys):
    engine = FakeEngine()
    assert run_app(repo, engine, "--out", str(tmp_path / "x")) == 1
    assert "must be inside" in capsys.readouterr().err
    assert engine.calls == []
