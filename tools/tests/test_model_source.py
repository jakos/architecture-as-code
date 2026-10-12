import contextlib
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import model_source
import submit

MODEL_PATH = "examples/shop"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "clone"
    model = root / MODEL_PATH
    (model / "views").mkdir(parents=True)
    (model / "model.c4").write_text("model {}\n")
    (model / "notes.md").write_text("not a model\n")
    (model / "views" / "v.c4").write_text("views {}\n")
    return root


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    ).stdout


def test_local_clone_source_satisfies_protocol(repo):
    source = model_source.LocalCloneSource(repo, MODEL_PATH)
    assert isinstance(source, model_source.ModelSource)
    for name in ("branch", "list_files", "read", "write", "changes", "workdir", "submit"):
        assert callable(getattr(source, name))
    assert source.workdir() == repo / MODEL_PATH


def test_local_clone_source_lists_only_c4_inside_model(repo, tmp_path):
    secret = tmp_path / "secret.c4"
    secret.write_text("secret\n")
    with contextlib.suppress(OSError, NotImplementedError):  # symlinks may be unavailable here
        (repo / MODEL_PATH / "link.c4").symlink_to(secret)
    (repo / "outside.c4").write_text("not in the model\n")
    source = model_source.LocalCloneSource(repo, MODEL_PATH)
    assert source.list_files() == ["model.c4", "views/v.c4"]
    with pytest.raises(model_source.SourceError) as err:
        source.read("../../outside.c4")
    assert err.value.status == 400
    with pytest.raises(model_source.SourceError) as err:
        source.read("notes.md")
    assert err.value.status == 400
    with pytest.raises(model_source.SourceError) as err:
        source.read("missing.c4")
    assert err.value.status == 404


def test_local_clone_source_write_is_atomic(repo, monkeypatch):
    source = model_source.LocalCloneSource(repo, MODEL_PATH)
    source.write("model.c4", "model { a }\n")
    assert source.read("model.c4") == "model { a }\n"
    model_dir = repo / MODEL_PATH
    assert [p.name for p in model_dir.iterdir() if p.name.endswith(".tmp")] == []

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(model_source.os, "replace", boom)
    with pytest.raises(OSError):
        source.write("model.c4", "lost")
    assert source.read("model.c4") == "model { a }\n"
    assert [p.name for p in model_dir.iterdir() if p.name.endswith(".tmp")] == []
    with pytest.raises(model_source.SourceError) as err:
        source.write("nope/x.c4", "x")
    assert err.value.status == 400


def test_local_clone_source_branch_reads_git(repo):
    git(repo, "init", "-b", "model/ada/2026-10-11-x")
    git(repo, "config", "user.name", "ada")
    git(repo, "config", "user.email", "ada@example.invalid")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "seed")
    source = model_source.LocalCloneSource(repo, MODEL_PATH)
    assert source.branch() == "model/ada/2026-10-11-x"
    assert source.changes() == []
    source.write("model.c4", "model { b }\n")
    assert [line.split()[-1] for line in source.changes()] == [f"{MODEL_PATH}/model.c4"]


def test_local_clone_source_submit_returns_output_and_model_relative_skipped(repo):
    def fake_submit(tool, path, repo_arg, message):
        print("pushed model/ada/2026-10-11-x to origin")
        print(f"skipped (not committed): {MODEL_PATH}/.likec4/x.likec4.snap")
        print("skipped (not committed): elsewhere/y.snap")

    source = model_source.LocalCloneSource(repo, MODEL_PATH, submit_fn=fake_submit)
    result = source.submit("msg")
    assert "pushed model/ada" in result.output
    assert result.skipped == [".likec4/x.likec4.snap", "elsewhere/y.snap"]


def test_local_clone_source_submit_error_is_a_422(repo):
    def refuse(*args):
        raise submit.SubmitError("refusing to submit from 'main'")

    source = model_source.LocalCloneSource(repo, MODEL_PATH, submit_fn=refuse)
    with pytest.raises(model_source.SourceError) as err:
        source.submit("msg")
    assert err.value.status == 422
    assert "refusing to submit from 'main'" in err.value.message
