import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import submit

BRANCH = "model/ada/2026-10-10-add-notifications"
REPO = Path("/clone")


class FakeRun:
    """Stands in for subprocess.run: records commands, answers from a script."""

    def __init__(self, branch=BRANCH, porcelain=" M model.c4\n", fail=None):
        self.branch = branch
        self.porcelain = porcelain
        self.fail = fail  # substring of a command whose exit code should be 1
        self.calls: list[list[str]] = []
        self.cwds: list[object] = []

    def __call__(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        self.cwds.append(kwargs.get("cwd"))
        line = " ".join(cmd)
        if "rev-parse" in cmd:
            out = self.branch + "\n"
        elif "status" in cmd:
            out = self.porcelain
        else:
            out = ""
        if self.fail and self.fail in line:
            return subprocess.CompletedProcess(cmd, 1, out, "validator said no\n")
        return subprocess.CompletedProcess(cmd, 0, out, "")

    def git_verbs(self) -> list[str]:
        return [c[3] for c in self.calls if c[0] == "git"]


def test_refuses_main():
    with pytest.raises(submit.SubmitError, match="main"):
        submit.check_branch("main")


@pytest.mark.parametrize(
    "branch",
    ["feature/x", "model/ada", "model/ada/add-notifications", "model/ada/2026-10-10-", "HEAD"],
)
def test_refuses_incomplete_model_branch(branch):
    with pytest.raises(submit.SubmitError, match="model/<user>/<yyyy-mm-dd>-<slug>"):
        submit.check_branch(branch)


def test_accepts_model_branch():
    assert submit.check_branch(BRANCH) == BRANCH


def test_refspec_targets_model_ref_only():
    assert submit.refspec(BRANCH) == f"HEAD:refs/heads/{BRANCH}"
    with pytest.raises(submit.SubmitError, match="refs/heads/model/"):
        submit.refspec("main")


def test_validator_commands_likec4():
    cmds = submit.validator_commands("likec4", "examples/shop")
    assert cmds == [["likec4", "validate"], ["likec4", "format", "--check"]]
    assert submit.validator_cwd(REPO, "examples/shop") == REPO / "examples/shop"


def test_validation_failure_stops_before_commit(capsys):
    run = FakeRun(fail="format --check")
    with pytest.raises(submit.SubmitError, match="validator said no"):
        submit.submit("likec4", "examples/shop", REPO, "msg", run=run)
    assert "add" not in run.git_verbs()
    assert "commit" not in run.git_verbs()
    assert "push" not in run.git_verbs()


def test_empty_change_is_refused():
    run = FakeRun(porcelain="")
    with pytest.raises(submit.SubmitError, match="nothing to submit"):
        submit.submit("likec4", "examples/shop", REPO, "msg", run=run)
    assert "commit" not in run.git_verbs()
    assert ["likec4", "validate"] not in run.calls


def test_refuses_to_submit_from_main_without_touching_git_state():
    run = FakeRun(branch="main")
    with pytest.raises(submit.SubmitError, match="main"):
        submit.submit("likec4", "examples/shop", REPO, "msg", run=run)
    assert run.git_verbs() == ["rev-parse"]


def test_pr_command_is_printed_not_run(capsys):
    run = FakeRun()
    submit.submit("likec4", "examples/shop", REPO, "Add notifications", run=run)
    out = capsys.readouterr().out
    assert f"gh pr create --base main --head {BRANCH} --title 'Add notifications'" in out
    assert "PR not opened" in out
    assert not any(c[0] == "gh" for c in run.calls)
    assert run.git_verbs() == ["rev-parse", "status", "add", "commit", "push"]
    assert run.calls[-1][-2:] == ["origin", f"HEAD:refs/heads/{BRANCH}"]


def test_commit_is_limited_to_the_model_path():
    run = FakeRun()
    submit.submit("likec4", "examples/shop", REPO, "msg", run=run)
    commit = next(c for c in run.calls if c[0] == "git" and "commit" in c)
    assert commit[-2:] == ["--", submit.model_pathspec("examples/shop")]


def test_staged_file_outside_path_is_not_committed(tmp_path):
    def git(*args, cwd):
        return subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
        ).stdout

    remote = tmp_path / "remote.git"
    clone = tmp_path / "clone"
    git("init", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    git("clone", str(remote), str(clone), cwd=tmp_path)
    for key, value in (("user.name", "ada"), ("user.email", "ada@example.invalid")):
        git("config", key, value, cwd=clone)
    (clone / "model").mkdir()
    (clone / "model" / "model.c4").write_text("a\n")
    (clone / "README.md").write_text("one\n")
    git("add", "-A", cwd=clone)
    git("commit", "-m", "seed", cwd=clone)
    git("push", "origin", "HEAD:main", cwd=clone)
    git("switch", "-c", BRANCH, cwd=clone)

    (clone / "model" / "model.c4").write_text("b\n")
    (clone / "README.md").write_text("two\n")
    git("add", "README.md", cwd=clone)

    real_run = subprocess.run

    def run(cmd, **kwargs):
        if cmd[0] == "likec4":  # the validator is not under test here
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, **kwargs)

    submit.submit("likec4", "model", clone, "msg", run=run)

    changed = git("show", "--name-only", "--format=", "HEAD", cwd=clone).split()
    assert changed == ["model/model.c4"]
    assert git("diff", "--cached", "--name-only", cwd=clone).split() == ["README.md"]


def _clone_with_model(tmp_path):
    """A clone on a model/* branch whose model dir holds a .c4 file, a tracked .snap and a
    .gitignore that hides .likec4/. Returns (clone, git, run)."""

    def git(*args, cwd=None):
        return subprocess.run(
            ["git", *args], cwd=cwd or clone, capture_output=True, text=True, check=True
        ).stdout

    remote = tmp_path / "remote.git"
    clone = tmp_path / "clone"
    git("init", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    git("clone", str(remote), str(clone), cwd=tmp_path)
    for key, value in (("user.name", "ada"), ("user.email", "ada@example.invalid")):
        git("config", key, value)
    (clone / "model").mkdir()
    (clone / "model" / "model.c4").write_text("a\n")
    (clone / "model" / "layout.snap").write_text("one\n")
    (clone / ".gitignore").write_text(".likec4/\n")
    git("add", "-A")
    git("commit", "-m", "seed")
    git("push", "origin", "HEAD:main")
    git("switch", "-c", BRANCH)

    real_run = subprocess.run

    def run(cmd, **kwargs):
        if cmd[0] == "likec4":  # the validator is not under test here
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real_run(cmd, **kwargs)

    return clone, git, run


def test_submit_stages_only_c4_files(tmp_path, capsys):
    clone, git, run = _clone_with_model(tmp_path)
    (clone / "model" / "model.c4").write_text("b\n")
    (clone / "model" / "new.c4").write_text("n\n")
    (clone / "model" / "views").mkdir()
    (clone / "model" / "views" / "v.c4").write_text("v\n")
    (clone / "model" / "notes.md").write_text("not a model\n")

    submit.submit("likec4", "model", clone, "msg", run=run)

    changed = sorted(git("show", "--name-only", "--format=", "HEAD").split())
    assert changed == ["model/model.c4", "model/new.c4", "model/views/v.c4"]
    assert "notes.md" in git("status", "--porcelain")


def test_submit_skips_and_reports_snap_changes(tmp_path, capsys):
    clone, git, run = _clone_with_model(tmp_path)
    (clone / "model" / "model.c4").write_text("b\n")
    (clone / "model" / "layout.snap").write_text("two\n")  # tracked, modified
    (clone / "model" / ".likec4").mkdir()
    (clone / "model" / ".likec4" / "x.likec4.snap").write_text("viewed only\n")  # ignored

    skipped = submit.submit("likec4", "model", clone, "msg", run=run)

    assert sorted(skipped) == ["model/.likec4/x.likec4.snap", "model/layout.snap"]
    out = capsys.readouterr().out
    assert "skipped (not committed): model/layout.snap" in out
    assert "skipped (not committed): model/.likec4/x.likec4.snap" in out
    assert git("show", "--name-only", "--format=", "HEAD").split() == ["model/model.c4"]
    assert git("diff", "--name-only").split() == ["model/layout.snap"]  # still modified


def test_submit_with_only_snap_changes_is_nothing_to_submit(tmp_path):
    clone, git, run = _clone_with_model(tmp_path)
    (clone / "model" / "layout.snap").write_text("two\n")
    (clone / "model" / ".likec4").mkdir()
    (clone / "model" / ".likec4" / "x.likec4.snap").write_text("viewed only\n")
    head = git("rev-parse", "HEAD")

    with pytest.raises(submit.SubmitError, match="nothing to submit"):
        submit.submit("likec4", "model", clone, "msg", run=run)

    assert git("rev-parse", "HEAD") == head


def test_submit_commit_pathspec_is_c4_only():
    run = FakeRun(porcelain=" M model.c4\n M layout.snap\n?? notes.md\n")
    submit.submit("likec4", "examples/shop", REPO, "msg", run=run)
    add = next(c for c in run.calls if c[0] == "git" and "add" in c)
    commit = next(c for c in run.calls if c[0] == "git" and "commit" in c)
    pathspec = ":(glob)examples/shop/**/*.c4"
    assert add[-2:] == ["--", pathspec]
    assert commit[-2:] == ["--", pathspec]
    status = next(c for c in run.calls if c[0] == "git" and "status" in c)
    assert "--ignored" in status


def test_deleted_c4_file_is_committed(tmp_path):
    clone, git, run = _clone_with_model(tmp_path)
    (clone / "model" / "model.c4").unlink()

    submit.submit("likec4", "model", clone, "msg", run=run)

    assert git("show", "--name-status", "--format=", "HEAD").split() == ["D", "model/model.c4"]
