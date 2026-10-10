"""Build the local PR-target remote for the B1 editor PoC without touching the host repo's git.

Two steps, because the host repository must never receive a commit or push:

  snapshot <src> <dest>      on the host: copy the files git would consider part of the tree
                             (tracked plus untracked-not-ignored, so an uncommitted port is
                             included; `.work/` and `build/` excluded). Reads git, writes none.
  seed <seed-dir> <bare>     inside an editor container: create the bare repo, commit the
                             snapshot as `main` with a fixed PoC identity, push `main` to it.

Stdlib only and no 3.14-only syntax: `seed` runs on the Python 3 shipped in the images.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

EXCLUDED_TOP_LEVEL = (".work", "build", ".git")

Runner = Callable[..., subprocess.CompletedProcess]


def tracked_and_untracked(src: Path, run: Runner = subprocess.run) -> list[str]:
    """Paths relative to src: tracked plus untracked-not-ignored, minus excluded dirs."""
    proc = run(
        ["git", "-C", str(src), "ls-files", "-co", "--exclude-standard", "-z"],
        capture_output=True,
        check=True,
    )
    names = [n.decode() for n in proc.stdout.split(b"\0") if n]
    return sorted(n for n in set(names) if n.split("/", 1)[0] not in EXCLUDED_TOP_LEVEL)


def snapshot(src: Path, dest: Path, run: Runner = subprocess.run) -> int:
    """Replace dest with a copy of src's files. Returns the number of files copied."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    copied = 0
    for name in tracked_and_untracked(src, run):
        source = src / name
        if not source.is_file():  # tracked but deleted in the working tree
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied


def seed(seed_dir: Path, bare: Path, env: dict[str, str], run: Runner = subprocess.run) -> None:
    """Recreate the bare repo at `bare` and push the seed tree to it as `main` only."""
    name = env.get("POC_AUTHOR_NAME", "PoC Seed")
    email = env.get("POC_AUTHOR_EMAIL", "poc-seed@example.invalid")
    if bare.exists():
        shutil.rmtree(bare)
    work = Path(tempfile.mkdtemp(prefix="poc-seed-"))
    try:
        shutil.copytree(seed_dir, work, dirs_exist_ok=True)
        # fileMode=false: bind mounts from a Windows host report every file as executable
        identity = ["-c", f"user.name={name}", "-c", f"user.email={email}"]
        git = ["git", "-c", "core.fileMode=false", *identity]
        for cmd in (
            ["git", "init", "--bare", "--initial-branch=main", str(bare)],
            [*git, "-C", str(work), "init", "--initial-branch=main"],
            [*git, "-C", str(work), "add", "-A"],
            [*git, "-C", str(work), "commit", "-m", "PoC seed: snapshot of the working tree"],
            [*git, "-C", str(work), "push", str(bare), "main:refs/heads/main"],
        ):
            run(cmd, check=True)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot", help="copy the tree into a seed directory (host)")
    snap.add_argument("src", type=Path)
    snap.add_argument("dest", type=Path)
    sd = sub.add_parser("seed", help="create the bare remote from a seed directory (container)")
    sd.add_argument("seed_dir", type=Path)
    sd.add_argument("bare", type=Path)
    args = parser.parse_args(argv)

    if args.command == "snapshot":
        count = snapshot(args.src, args.dest)
        print(f"snapshot: {count} files copied to {args.dest}")
    else:
        seed(args.seed_dir, args.bare, dict(os.environ))
        print(f"seeded {args.bare} with main from {args.seed_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
