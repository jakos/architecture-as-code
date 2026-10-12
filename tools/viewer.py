"""Build read-only static sites of the LikeC4 model for `main`, branches and pull requests.

`build [REF ...]` exports a project from a git commit (`git archive`, never the working tree),
builds it with `likec4 build` in a container and puts the site under
`<out>/site/<main|branch/NAME|pr/N>/`. REF is `main` (default), `pr/<n>` or a local branch name.
It also keeps `<out>/site/refs/` (a manifest and an HTML list of the built refs). Serve
`<out>/site` with any static file server (`just viewer-up`).

`pages --base BASE [--ref REF]` builds one site (default ref `HEAD`) for GitHub Pages: the site
goes at the root of `--out` (default `build/pages`, which must be inside `<repo>/build/`) and
is served under BASE, for example `/architecture-as-code/`. It writes no `refs/` manifest and
replaces the whole `--out` directory, so `editor/` is left free for a later build into
`<out>/editor/`.

The tool never writes outside `--out`, never changes the host repo's working tree, `HEAD` or
refs (a PR is fetched into FETCH_HEAD only), and never commits, pushes or checks out.
"""

import argparse
import html
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_models import CONFIG_NAME, IMAGE, REPO

DEFAULT_OUT = "build/viewer"
DEFAULT_PAGES_OUT = "build/pages"
SAFE_REF = re.compile(r"[A-Za-z0-9._/-]+")
SAFE_SEGMENT = re.compile(r"[A-Za-z0-9._-]+")
Runner = Callable[..., "subprocess.CompletedProcess"]


class ViewerError(Exception):
    """A failure to report to the user as one line, exit code 1."""


@dataclass(frozen=True)
class Target:
    kind: str  # main | branch | pr
    name: str  # the ref as the user typed it
    url_path: str  # directory below the site root, with a trailing slash


def parse_ref(text: str) -> Target:
    """Map a ref to its URL path. Rejects anything unsafe before git is called."""
    if not text:
        raise ViewerError("empty ref")
    if text.startswith("-"):
        raise ViewerError(f"invalid ref (leading '-'): {text}")
    if not SAFE_REF.fullmatch(text):
        raise ViewerError(f"invalid ref (allowed characters: A-Z a-z 0-9 . _ / -): {text}")
    if ".." in text or "//" in text or text.endswith("/"):
        raise ViewerError(f"invalid ref: {text}")
    if any(part.startswith(".") for part in text.split("/")):
        raise ViewerError(f"invalid ref (segment starts with '.'): {text}")
    if text == "main":
        return Target("main", text, "main/")
    if text.startswith("pr/"):
        number = text[3:]
        if not number.isascii() or not number.isdigit():
            raise ViewerError(f"invalid pull request ref (want pr/<number>): {text}")
        return Target("pr", text, f"pr/{number}/")
    return Target("branch", text, f"branch/{text}/")


def _git(run: Runner, repo: Path, *args: str) -> subprocess.CompletedProcess:
    return run(["git", *args], cwd=repo, capture_output=True, check=False)


def resolve_commit(repo: Path, target: Target, remote: str, run: Runner = subprocess.run) -> str:
    """The commit sha for a target. Creates no ref: PRs are fetched into FETCH_HEAD only."""
    if target.kind == "pr":
        if remote.startswith("-"):
            raise ViewerError(f"invalid remote: {remote}")
        number = target.name[3:]
        fetch = _git(run, repo, "fetch", "--no-tags", "--", remote, f"refs/pull/{number}/head")
        if fetch.returncode != 0:
            raise ViewerError(f"unknown ref: {target.name}")
        candidates = ["FETCH_HEAD"]
    else:
        candidates = [f"refs/heads/{target.name}", target.name]
    for candidate in candidates:
        found = _git(run, repo, "rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}")
        if found.returncode == 0 and found.stdout.strip():
            return found.stdout.decode().strip()
    raise ViewerError(f"unknown ref: {target.name}")


def export_project(
    repo: Path, commit: str, project: str, dest: Path, run: Runner = subprocess.run
) -> Path:
    """Extract `project` as of `commit` into dest; returns the project directory."""
    archive = _git(run, repo, "archive", "--format=tar", commit, "--", project)
    if archive.returncode != 0:
        raise ViewerError(f"project {project} not found at {commit[:7]}")
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
        tar.extractall(dest, filter="data")
    root = dest / project
    if not (root / CONFIG_NAME).is_file():
        raise ViewerError(f"{project}/{CONFIG_NAME} not found at {commit[:7]}")
    return root


def build_command(engine: str, src: Path, dest: Path, base: str, title: str) -> list[str]:
    """likec4 build with the project mounted read-only; the site is served under `base`."""
    return [
        engine,
        "run",
        "--rm",
        "-v",
        f"{src}:/data:ro",
        "-v",
        f"{dest}:/out",
        IMAGE,
        "build",
        "-o",
        "/out",
        "--base",
        base,
        "--use-hash-history",
        "--title",
        title,
    ]


def swap_in(new: Path, target: Path) -> None:
    """Replace target with new: rename the old one away, rename the new one in, delete the old."""
    target.parent.mkdir(parents=True, exist_ok=True)
    old = target.with_name(f"{target.name}.old-{os.getpid()}")
    had_old = target.exists()
    if had_old:
        target.rename(old)
    try:
        new.rename(target)
    except OSError:
        if had_old:
            old.rename(target)
        raise
    if had_old:
        shutil.rmtree(old, ignore_errors=True)


def _load_manifest(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def _sort_key(entry: dict) -> tuple[int, str]:
    return (0 if entry.get("ref") == "main" else 1, str(entry.get("ref", "")))


def write_refs_index(site: Path) -> None:
    """Regenerate refs/index.html from refs/refs.json: main first, then sorted."""
    refs_dir = site / "refs"
    entries = sorted(_load_manifest(refs_dir / "refs.json"), key=_sort_key)
    items = []
    for e in entries:
        href = "../" + quote(str(e.get("path", "")))
        items.append(
            f'    <li><a href="{html.escape(href, quote=True)}">{html.escape(str(e.get("ref")))}'
            f"</a> <code>{html.escape(str(e.get('commit', ''))[:7])}</code> "
            f"built {html.escape(str(e.get('built_at', '')))}</li>"
        )
    body = "\n".join(items) or "    <li>nothing built yet</li>"
    page = (
        '<!doctype html>\n<html lang="en">\n<head><meta charset="utf-8">'
        "<title>Built refs</title></head>\n<body>\n<h1>Built refs</h1>\n<ul>\n"
        f"{body}\n</ul>\n</body>\n</html>\n"
    )
    (refs_dir / "index.html").write_text(page, encoding="utf-8")


def record_ref(site: Path, target: Target, commit: str) -> None:
    refs_dir = site / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    manifest = refs_dir / "refs.json"
    # Swapping in target replaces its whole directory, so nested refs' sites are gone.
    entries = [
        e
        for e in _load_manifest(manifest)
        if e.get("ref") != target.name and not str(e.get("path", "")).startswith(target.url_path)
    ]
    entries.append(
        {
            "ref": target.name,
            "kind": target.kind,
            "path": target.url_path,
            "commit": commit,
            "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        }
    )
    entries.sort(key=_sort_key)
    manifest.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    write_refs_index(site)


def check_not_inside_other_ref(site: Path, target: Target) -> None:
    """Refuse to build into the directory of another built ref (a/b while a is built)."""
    for e in _load_manifest(site / "refs" / "refs.json"):
        other = str(e.get("path", ""))
        if e.get("ref") != target.name and target.url_path.startswith(other):
            raise ViewerError(
                f"cannot build {target.name}: its path is inside the site of {e.get('ref')}"
            )


@contextmanager
def built_site(
    *,
    ref: str,
    commit: str,
    repo: Path,
    project: str,
    engine: str,
    base: str,
    tmp_parent: Path,
    run: Runner,
) -> Iterator[Path]:
    """Export the project at `commit` and build it; yields the directory holding the site.

    The directory lives in a temp dir below `tmp_parent` that is removed on exit, so the caller
    must move the site out (`swap_in`) before leaving the block.
    """
    tmp_parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="work-", dir=tmp_parent)).resolve()
    try:
        src = export_project(repo, commit, project, work / "src", run)
        dest = work / "site"
        dest.mkdir()
        title = f"{Path(project).name} @ {ref} ({commit[:7]})"
        cmd = build_command(engine, src, dest, base, title)
        if run(cmd, check=False).returncode != 0 or not (dest / "index.html").is_file():
            raise ViewerError(f"build failed for {ref}; previous site kept")
        yield dest
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_ref(
    ref: str,
    *,
    repo: Path,
    project: str,
    engine: str,
    remote: str,
    out: Path,
    run: Runner = subprocess.run,
) -> None:
    target = parse_ref(ref)
    commit = resolve_commit(repo, target, remote, run)
    check_not_inside_other_ref(out.resolve() / "site", target)
    with built_site(
        ref=target.name,
        commit=commit,
        repo=repo,
        project=project,
        engine=engine,
        base=f"/{target.url_path}",
        tmp_parent=out,
        run=run,
    ) as dest:
        site = out.resolve() / "site"
        swap_in(dest, site / target.url_path.rstrip("/"))
        record_ref(site, target, commit)
    print(f"built {ref} ({commit[:7]}) -> {out.as_posix()}/site/{target.url_path}", flush=True)


def check_base(base: str) -> None:
    """A base is `/` or `/seg/.../`, each segment made of [A-Za-z0-9._-], none `.`, `..` or `-x`."""
    if len(base) < 1 or not base.startswith("/") or not base.endswith("/"):
        raise ViewerError(f"invalid base (must start and end with '/'): {base}")
    if base == "/":
        return
    for segment in base[1:-1].split("/"):
        if not SAFE_SEGMENT.fullmatch(segment) or segment in (".", "..") or segment.startswith("-"):
            raise ViewerError(f"invalid base (bad segment {segment!r}): {base}")


def check_pages_out(repo: Path, out: Path) -> None:
    """The swap replaces the whole directory, so `out` must be strictly inside <repo>/build/."""
    build = (repo / "build").resolve()
    if build not in out.resolve().parents:
        raise ViewerError(f"refusing --out {out}: must be inside {build.as_posix()}/")


def build_pages(
    ref: str,
    *,
    repo: Path,
    project: str,
    engine: str,
    remote: str,
    base: str,
    out: Path,
    run: Runner = subprocess.run,
) -> None:
    target = parse_ref(ref)
    check_base(base)
    check_pages_out(repo, out)
    commit = resolve_commit(repo, target, remote, run)
    with built_site(
        ref=target.name,
        commit=commit,
        repo=repo,
        project=project,
        engine=engine,
        base=base,
        tmp_parent=out.resolve().parent,
        run=run,
    ) as dest:
        swap_in(dest, out.resolve())
    print(f"built {ref} ({commit[:7]}) -> {out.as_posix()}/", flush=True)


def main(argv: list[str] | None = None, run: Runner = subprocess.run) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build", help="build the site of one or more refs")
    build.add_argument("refs", nargs="*", metavar="REF", help="main, pr/<n> or a branch")
    build.add_argument("--project", default=os.environ.get("MODEL", "examples/shop"))
    build.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE", "podman"))
    build.add_argument("--remote", default="origin", help="remote that serves refs/pull/<n>/head")
    build.add_argument("--out", default=DEFAULT_OUT)
    build.add_argument("--repo", default=str(REPO), help=argparse.SUPPRESS)
    pages = sub.add_parser("pages", help="build one site at the root of --out for GitHub Pages")
    pages.add_argument("--ref", default="HEAD", help="main, pr/<n>, a branch or HEAD (default)")
    pages.add_argument("--base", required=True, help="URL path of the site, e.g. /name/")
    pages.add_argument("--project", default=os.environ.get("MODEL", "examples/shop"))
    pages.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE", "podman"))
    pages.add_argument("--remote", default="origin", help="remote that serves refs/pull/<n>/head")
    pages.add_argument("--out", default=DEFAULT_PAGES_OUT)
    pages.add_argument("--repo", default=str(REPO), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    out = Path(args.out)
    if not out.is_absolute():
        out = repo / out
    if args.command == "pages":
        try:
            build_pages(
                args.ref,
                repo=repo,
                project=args.project.replace("\\", "/").strip("/"),
                engine=args.engine,
                remote=args.remote,
                base=args.base,
                out=out,
                run=run,
            )
        except ViewerError as err:
            print(str(err), file=sys.stderr)
            return 1
        return 0
    failed = False
    for ref in args.refs or ["main"]:
        try:
            build_ref(
                ref,
                repo=repo,
                project=args.project.replace("\\", "/").strip("/"),
                engine=args.engine,
                remote=args.remote,
                out=out,
                run=run,
            )
        except ViewerError as err:
            print(str(err), file=sys.stderr)
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
