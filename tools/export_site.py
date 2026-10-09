"""Export every workspace as a static Structurizr site under build/site/<name>/.

Writes build/site/index.html linking to each workspace, so the whole directory can be
served as-is (locally by `just site`, later by GitHub Pages).
"""

import argparse
import html
import os
import shutil
import subprocess
import sys
from pathlib import Path

from validate_workspaces import DEFAULT_ROOTS, IMAGE, REPO, find_workspaces

OUT = REPO / "build" / "site"


def site_name(repo: Path, workspace: Path) -> str:
    """examples/shop/workspace.dsl -> examples-shop"""
    return "-".join(workspace.parent.relative_to(repo).parts)


def export_command(engine: str, repo: Path, workspace: Path, name: str) -> list[str]:
    rel = workspace.relative_to(repo).as_posix()
    return [
        engine, "run", "--rm",
        "-v", f"{repo}:/repo",
        IMAGE, "export", "-f", "static",
        "-w", f"/repo/{rel}",
        "-o", f"/repo/build/site/{name}",
    ]  # fmt: skip


def index_html(names: list[str]) -> str:
    items = "\n".join(
        f'    <li><a href="{html.escape(n)}/">{html.escape(n)}</a></li>' for n in names
    )
    return (
        "<!doctype html>\n<meta charset=utf-8>\n<title>Architecture</title>\n"
        f"<h1>Architecture</h1>\n<ul>\n{items}\n</ul>\n"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="*", default=DEFAULT_ROOTS, help="dirs to search")
    parser.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE", "podman"))
    args = parser.parse_args(argv)

    workspaces = find_workspaces(REPO, tuple(args.roots))
    if not workspaces:
        print("no workspace.dsl found", file=sys.stderr)
        return 1

    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    names = []
    for ws in workspaces:
        name = site_name(REPO, ws)
        print(f"exporting {name}")
        cmd = export_command(args.engine, REPO, ws, name)
        if subprocess.run(cmd, check=False).returncode != 0:
            print(f"FAILED: {name}", file=sys.stderr)
            return 1
        names.append(name)

    (OUT / "index.html").write_text(index_html(names), encoding="utf-8")
    print(f"site: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
