"""Validate every Structurizr workspace in the repo with the structurizr/structurizr image.

Runs `structurizr validate` once per workspace.dsl found under the given roots, inside a
container, so nobody needs Java installed. Exits non-zero if any workspace fails.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Pinned: a new Structurizr release can change DSL parsing, so upgrading is its own change.
IMAGE = "docker.io/structurizr/structurizr:2026.09.19"
DEFAULT_ROOTS = ("examples", "workspaces")


def find_workspaces(repo: Path, roots: tuple[str, ...]) -> list[Path]:
    """Every workspace.dsl under the roots, skipping Structurizr's own .structurizr dirs."""
    found: list[Path] = []
    for root in roots:
        base = repo / root
        if base.is_dir():
            found += [p for p in base.rglob("workspace.dsl") if ".structurizr" not in p.parts]
    return sorted(found)


def validate_command(engine: str, repo: Path, workspace: Path) -> list[str]:
    rel = workspace.relative_to(repo).as_posix()
    return [
        engine, "run", "--rm",
        "-v", f"{repo}:/repo:ro",
        IMAGE, "validate", "-w", f"/repo/{rel}",
    ]  # fmt: skip


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", default=DEFAULT_ROOTS, help="dirs to search")
    parser.add_argument(
        "--engine",
        default=os.environ.get("CONTAINER_ENGINE", "podman"),
        help="container engine (default: $CONTAINER_ENGINE or podman)",
    )
    args = parser.parse_args(argv)

    workspaces = find_workspaces(REPO, tuple(args.roots))
    if not workspaces:
        print("no workspace.dsl found", file=sys.stderr)
        return 1

    failed = []
    for ws in workspaces:
        rel = ws.relative_to(REPO).as_posix()
        print(f"validating {rel}")
        result = subprocess.run(validate_command(args.engine, REPO, ws), check=False)
        if result.returncode != 0:
            failed.append(rel)

    if failed:
        print(f"FAILED: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"ok: {len(workspaces)} workspace(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
