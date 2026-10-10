import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import poc_remote


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_snapshot_copies_untracked_but_not_ignored(tmp_path):
    src = tmp_path / "src"
    (src / "trial").mkdir(parents=True)
    (src / "build").mkdir()
    (src / ".work").mkdir()
    _git(tmp_path, "init", str(src))
    (src / ".gitignore").write_text("ignored.txt\n")
    (src / "tracked.txt").write_text("tracked")
    (src / "ignored.txt").write_text("ignored")
    (src / "trial" / "model.c4").write_text("untracked port")
    (src / "build" / "x").write_text("build output")
    (src / ".work" / "plan.md").write_text("task files")
    _git(src, "add", ".gitignore", "tracked.txt")  # staged, never committed
    (src / "gone.txt").write_text("deleted later")
    _git(src, "add", "gone.txt")
    (src / "gone.txt").unlink()

    dest = tmp_path / "seed"
    dest.mkdir()
    (dest / "stale.txt").write_text("from a previous snapshot")
    count = poc_remote.snapshot(src, dest)

    copied = sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file())
    assert copied == [".gitignore", "tracked.txt", "trial/model.c4"]
    assert count == 3


def test_seed_pushes_main_only_to_the_given_bare_path(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "a.txt").write_text("a")
    bare = tmp_path / "remote.git"
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    poc_remote.seed(seed_dir, bare, {"POC_AUTHOR_NAME": "Seeder"}, run=fake_run)

    verbs = [c[c.index("-C") + 2] if "-C" in c else c[1] for c in calls]
    assert verbs == ["init", "init", "add", "commit", "push"]
    assert calls[0] == ["git", "init", "--bare", "--initial-branch=main", str(bare)]
    assert "user.name=Seeder" in calls[3]
    pushes = [c for c in calls if "push" in c]
    assert len(pushes) == 1
    assert pushes[0][-2:] == [str(bare), "main:refs/heads/main"]
