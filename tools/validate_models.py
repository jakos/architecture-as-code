"""Validate every LikeC4 project in the repo with the likec4 image.

A project is a directory with a likec4.config.json. For each one under the given roots this
runs `likec4 validate` and `likec4 format --check` inside a container, so nobody needs Node
installed. Exits non-zero if any project fails.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Pinned: a new LikeC4 release can change parsing and formatting, so upgrading is its own change.
IMAGE = "docker.io/likec4/likec4:1.59.4"
DEFAULT_ROOTS = ("examples", "workspaces")
SKIP_DIRS = (".likec4", "node_modules", "build")
CONFIG_NAME = "likec4.config.json"


def find_projects(repo: Path, roots: tuple[str, ...]) -> list[Path]:
    """Every directory holding a likec4.config.json under the roots (absolute roots allowed)."""
    found: list[Path] = []
    for root in roots:
        base = repo / root  # an absolute root replaces the repo prefix
        if base.is_dir():
            found += [
                p.parent
                for p in base.rglob(CONFIG_NAME)
                if not any(part in SKIP_DIRS for part in p.relative_to(base).parts)
            ]
    return sorted(found)


def validate_commands(engine: str, project: Path) -> list[list[str]]:
    """Validate, then format --check, with the project mounted read-only at /data."""
    base = [engine, "run", "--rm", "-v", f"{project}:/data:ro", IMAGE]
    return [[*base, "validate"], [*base, "format", "--check"]]


def display(project: Path) -> str:
    try:
        return project.relative_to(REPO).as_posix()
    except ValueError:
        return project.as_posix()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", default=DEFAULT_ROOTS, help="dirs to search")
    parser.add_argument(
        "--engine",
        default=os.environ.get("CONTAINER_ENGINE", "podman"),
        help="container engine (default: $CONTAINER_ENGINE or podman)",
    )
    args = parser.parse_args(argv)

    projects = find_projects(REPO, tuple(args.roots))
    if not projects:
        print("no likec4 project found", file=sys.stderr)
        return 1

    failed = []
    for project in projects:
        name = display(project)
        print(f"validating {name}", flush=True)
        for cmd in validate_commands(args.engine, project):
            if subprocess.run(cmd, check=False).returncode != 0:
                failed.append(name)
                break

    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"ok: {len(projects)} project(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
