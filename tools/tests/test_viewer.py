import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import viewer
from validate_models import CONFIG_NAME, IMAGE
from viewer import ViewerError, build_command, parse_ref

PROJECT = "examples/shop"
IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *IDENTITY, *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def commit_model(repo: Path, content: str, message: str = "model") -> str:
    project = repo / PROJECT
    project.mkdir(parents=True, exist_ok=True)
    (project / CONFIG_NAME).write_text("{}")
    (project / "model.c4").write_text(content)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    git(path, "init", "-q", "-b", "main")
    (path / ".gitignore").write_text("build/\n")
    commit_model(path, "main content")
    return path


class FakeRunner:
    """Real git; the container run writes an index.html (or fails) into the /out mount."""

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.builds: list[list[str]] = []
        self.exported: list[str] = []

    def __call__(self, cmd, **kwargs):
        if cmd[0] == "git":
            return subprocess.run(cmd, **kwargs)
        self.builds.append(cmd)
        if self.fail:
            return subprocess.CompletedProcess(cmd, 1)
        src = Path(next(a for a in cmd if a.endswith(":/data:ro")).removesuffix(":/data:ro"))
        out = Path(next(a for a in cmd if a.endswith(":/out")).removesuffix(":/out"))
        self.exported.append((src / "model.c4").read_text())
        (out / "index.html").write_text(f"site of {(src / 'model.c4').read_text()}")
        return subprocess.CompletedProcess(cmd, 0)


def run_build(repo: Path, *refs: str, runner=None, remote="origin") -> int:
    return viewer.main(
        ["build", *refs, "--project", PROJECT, "--repo", str(repo), "--remote", remote],
        run=runner or FakeRunner(),
    )


def snapshot(repo: Path) -> tuple[str, str, str]:
    return (
        git(repo, "status", "--porcelain"),
        git(repo, "rev-parse", "HEAD"),
        git(repo, "for-each-ref"),
    )


def test_parse_ref_main_branch_pr():
    assert parse_ref("main") == viewer.Target("main", "main", "main/")
    assert parse_ref("feature/x").url_path == "branch/feature/x/"
    assert parse_ref("feature/x").kind == "branch"
    pr = parse_ref("pr/12")
    assert (pr.kind, pr.name, pr.url_path) == ("pr", "pr/12", "pr/12/")


@pytest.mark.parametrize("ref", ["-x", "a..b", "a b", "pr/abc", "pr/", "a//b", "a/", ".hidden", ""])
def test_parse_ref_rejects_unsafe(ref):
    with pytest.raises(ViewerError):
        parse_ref(ref)


def test_build_command_pinned_image_base_readonly_mount(tmp_path):
    cmd = build_command("podman", tmp_path / "src", tmp_path / "dest", "/branch/feature/x/", "t")
    assert IMAGE in cmd
    assert f"{tmp_path / 'src'}:/data:ro" in cmd
    assert cmd[cmd.index("--base") + 1] == "/branch/feature/x/"
    assert "--use-hash-history" in cmd


def test_exports_project_at_branch_commit(repo):
    git(repo, "checkout", "-q", "-b", "feature/a")
    commit_model(repo, "content a")
    git(repo, "checkout", "-q", "-b", "feature/b", "main")
    commit_model(repo, "content b")
    git(repo, "checkout", "-q", "main")
    runner = FakeRunner()
    assert run_build(repo, "feature/a", "feature/b", "main", runner=runner) == 0
    assert runner.exported == ["content a", "content b", "main content"]
    site = repo / "build" / "viewer" / "site"
    assert (site / "branch/feature/a/index.html").read_text() == "site of content a"
    assert (site / "main/index.html").is_file()


def test_export_leaves_repo_untouched(repo, tmp_path):
    git(repo, "checkout", "-q", "-b", "feature/a")
    commit_model(repo, "content a")
    git(repo, "checkout", "-q", "main")
    remote = make_remote(tmp_path, repo, 7, "content pr")
    git(repo, "remote", "add", "origin", str(remote))
    (repo / "scratch.txt").write_text("untracked")
    before = snapshot(repo)
    assert run_build(repo, "feature/a", "pr/7") == 0
    # build/viewer is not ignored in this temp repo, so compare ignoring it
    after = snapshot(repo)
    assert after[1:] == before[1:]
    assert after[0].replace("?? build/\n", "").replace("?? build/", "").strip() == before[0]


def make_remote(tmp_path: Path, repo: Path, number: int, content: str) -> Path:
    """A bare repo whose refs/pull/<n>/head holds a commit the local repo does not have."""
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    other = tmp_path / "other"
    git(tmp_path, "clone", "-q", str(repo), str(other))
    commit_model(other, content, "pr change")
    git(other, "push", "-q", str(remote), f"HEAD:refs/pull/{number}/head")
    return remote


def test_pr_ref_fetched_from_remote(repo, tmp_path):
    remote = make_remote(tmp_path, repo, 7, "content pr")
    git(repo, "remote", "add", "origin", str(remote))
    runner = FakeRunner()
    assert run_build(repo, "pr/7", runner=runner) == 0
    assert runner.exported == ["content pr"]
    assert (repo / "build/viewer/site/pr/7/index.html").is_file()
    assert "refs/pull" not in git(repo, "for-each-ref")


def test_unknown_ref_exits_1(repo, capsys):
    assert run_build(repo, "nope") == 1
    assert "unknown ref: nope" in capsys.readouterr().err
    assert run_build(repo, "pr/9", remote="missing") == 1
    assert "unknown ref: pr/9" in capsys.readouterr().err


def test_missing_project_at_ref_fails(repo, capsys):
    git(repo, "checkout", "-q", "-b", "empty")
    git(repo, "rm", "-rq", PROJECT)
    git(repo, "commit", "-q", "-m", "drop model")
    runner = FakeRunner()
    assert run_build(repo, "empty", runner=runner) == 1
    assert "not found" in capsys.readouterr().err
    assert runner.builds == []


def test_failed_build_keeps_previous_site(repo):
    assert run_build(repo, "main") == 0
    index = repo / "build/viewer/site/main/index.html"
    assert index.read_text() == "site of main content"
    git(repo, "checkout", "-q", "-b", "other")
    commit_model(repo, "new content")
    git(repo, "branch", "-f", "main", "other")
    assert run_build(repo, "main", runner=FakeRunner(fail=True)) == 1
    assert index.read_text() == "site of main content"
    assert not list((repo / "build/viewer/site").glob("main.old-*"))


def test_refs_index_lists_main_first_and_escapes(repo, tmp_path):
    git(repo, "branch", "aaa")
    assert run_build(repo, "aaa", "main") == 0
    site = repo / "build/viewer/site"
    manifest = site / "refs" / "refs.json"
    entries = json.loads(manifest.read_text())
    assert {"ref", "kind", "path", "commit", "built_at"} <= set(entries[0])
    entries.append(
        {"ref": "<b>x</b>", "kind": "branch", "path": "branch/x/", "commit": "1234567890"}
    )
    manifest.write_text(json.dumps(entries))
    viewer.write_refs_index(site)
    page = (site / "refs" / "index.html").read_text()
    assert page.index(">main<") < page.index(">aaa<")
    assert "&lt;b&gt;x&lt;/b&gt;" in page
    assert "<b>x</b>" not in page


def test_nested_branch_rebuilt_as_parent_keeps_manifest_and_disk_in_sync(repo):
    git(repo, "branch", "a/b")
    assert run_build(repo, "a/b") == 0
    git(repo, "branch", "-D", "a/b")
    git(repo, "branch", "a")
    assert run_build(repo, "a") == 0
    site = repo / "build" / "viewer" / "site"
    manifest = json.loads((site / "refs" / "refs.json").read_text())
    assert [e["ref"] for e in manifest] == ["a"]
    for e in manifest:
        assert (site / e["path"] / "index.html").is_file()
    assert not (site / "branch" / "a" / "b").exists()


def test_build_inside_another_ref_is_refused(repo, capsys):
    git(repo, "branch", "a")
    assert run_build(repo, "a") == 0
    git(repo, "branch", "-D", "a")
    git(repo, "branch", "a/b")
    assert run_build(repo, "a/b") == 1
    assert "inside the site of a" in capsys.readouterr().err
    site = repo / "build" / "viewer" / "site"
    assert [e["ref"] for e in json.loads((site / "refs" / "refs.json").read_text())] == ["a"]


PAGES_BASE = "/architecture-as-code/"


def run_pages(repo: Path, *extra: str, runner=None, base: str = PAGES_BASE) -> int:
    return viewer.main(
        ["pages", f"--base={base}", "--project", PROJECT, "--repo", str(repo), *extra],
        run=runner or FakeRunner(),
    )


def test_pages_builds_site_at_out_root(repo):
    runner = FakeRunner()
    assert run_pages(repo, runner=runner) == 0
    out = repo / "build" / "pages"
    assert (out / "index.html").read_text() == "site of main content"
    cmd = runner.builds[0]
    assert cmd[cmd.index("--base") + 1] == PAGES_BASE
    assert "--use-hash-history" in cmd
    assert not (out / "refs").exists()
    assert not (out / "editor").exists()
    assert list((repo / "build").iterdir()) == [out]


def test_pages_default_ref_is_head(repo):
    commit_model(repo, "head content")
    git(repo, "checkout", "-q", "--detach", "HEAD")
    git(repo, "branch", "-f", "main", "HEAD~1")
    runner = FakeRunner()
    assert run_pages(repo, runner=runner) == 0
    assert runner.exported == ["head content"]


@pytest.mark.parametrize(
    "base", ["architecture-as-code", "/a", "a/", "/../", "/a b/", "/a//b/", "-x/", "/./", "/-x/"]
)
def test_pages_rejects_bad_base(repo, capsys, base):
    runner = FakeRunner()
    assert run_pages(repo, runner=runner, base=base) == 1
    assert "invalid base" in capsys.readouterr().err
    assert runner.builds == []
    assert not (repo / "build").exists()


def test_pages_refuses_out_outside_build(repo, tmp_path, capsys):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    before = snapshot(repo)
    for out in (str(repo), "build", str(outside), "build/.."):
        runner = FakeRunner()
        assert run_pages(repo, "--out", out, runner=runner) == 1
        assert "refusing --out" in capsys.readouterr().err
        assert runner.builds == []
    assert snapshot(repo) == before
    assert (outside / "keep.txt").read_text() == "keep"
    assert not (repo / "build").exists()


def test_pages_failed_build_keeps_previous_site(repo, capsys):
    assert run_pages(repo) == 0
    commit_model(repo, "newer content")
    assert run_pages(repo, runner=FakeRunner(fail=True)) == 1
    assert "build failed" in capsys.readouterr().err
    assert (repo / "build/pages/index.html").read_text() == "site of main content"
    assert [p.name for p in (repo / "build").iterdir()] == ["pages"]
