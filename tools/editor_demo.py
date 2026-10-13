"""Build the static demo of the model editor for GitHub Pages, under `<pages>/editor/`.

The demo is the model editor's own app (the LikeC4 playground plus our patches) built in the
Vite mode `demo`: no server, nothing is saved, the model is read from a `workspace.json` that
sits next to `index.html`. Two steps, because the app build takes minutes and the model changes
often:

  app --base BASE [--out build/editor-demo-app]
      builds the `demo` stage of docker/editor/model-editor/Containerfile with the container
      engine, copies the static files out of it and checks them.
  assemble --base BASE [--ref main] [--project examples/shop] [--app build/editor-demo-app]
           [--out build/pages/editor] [--optional]
      checks the app files, exports the `.c4` files of the project at a git ref into
      `workspace.json` (committed text, never the working tree) and puts both into --out.

BASE is the URL path the demo is served under, for example `/architecture-as-code/editor/`.
`--out` must be inside `<repo>/build/` and is replaced as a whole. Run `assemble` after
`viewer.py pages`, which replaces the whole of `build/pages`.

The bundle check refuses to publish files that refer to another origin or to a path outside
BASE, hold Python, or contain a call to the editor server's API. The tool never commits,
pushes or changes the repo.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import viewer
from validate_models import CONFIG_NAME, REPO
from viewer import Runner, ViewerError

CONTAINERFILE = "docker/editor/model-editor/Containerfile"
IMAGE_TAG = "localhost/aac-editor-demo:v1.59.4"
DEFAULT_APP = "build/editor-demo-app"
DEFAULT_OUT = "build/pages/editor"
MODEL_SUFFIX = ".c4"
# Paths of the editor server's API. None of them may be in the published files.
API_PATHS = (
    b"/api/workspace",
    b"/api/file",
    b"/api/status",
    b"/api/validate",
    b"/api/format",
    b"/api/submit",
)
URL_ATTR = re.compile(r"""\b(?:src|href)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.IGNORECASE)


def check_bundle(app: Path, base: str) -> None:
    """Raise ViewerError (one line) unless `app` is a static app that is safe to publish."""
    index = app / "index.html"
    if not index.is_file():
        raise ViewerError(f"demo app incomplete: {index.as_posix()} not found")
    text = index.read_text(encoding="utf-8")
    for match in URL_ATTR.finditer(text):
        url = match.group(1) if match.group(1) is not None else match.group(2)
        if url.startswith("data:"):
            continue
        if not url.startswith(base) or url.startswith("//"):
            raise ViewerError(f"demo app refers to {url!r} in index.html, outside {base}")
    for path in sorted(app.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(app).as_posix()
        if path.suffix == ".py":
            raise ViewerError(f"demo app holds a Python file: {rel}")
        data = path.read_bytes()
        for api in API_PATHS:
            if api in data:
                raise ViewerError(f"demo app calls the editor server API {api.decode()}: {rel}")


def read_model_files(
    repo: Path, commit: str, project: str, run: Runner = subprocess.run
) -> dict[str, str]:
    """The committed `.c4` files of `project` at `commit`: relative POSIX path -> text.

    Reads the blobs themselves, so the text is byte-equal to the commit whatever the checkout's
    line-ending settings are. Symlinks and non-UTF-8 files are refused.
    """
    listing = run(
        ["git", "ls-tree", "-r", "-z", commit, "--", f"{project}/"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if listing.returncode != 0:
        raise ViewerError(f"project {project} not found at {commit[:7]}")
    files: dict[str, str] = {}
    config_found = False
    for entry in listing.stdout.decode("utf-8").split("\0"):
        if not entry:
            continue
        meta, _, path = entry.partition("\t")
        mode, kind, _sha = meta.split()
        rel = path.removeprefix(f"{project}/")
        if rel == CONFIG_NAME:
            config_found = True
        if kind != "blob" or not rel.endswith(MODEL_SUFFIX):
            continue
        if mode not in ("100644", "100755"):
            raise ViewerError(f"{path} is not a regular file")
        blob = run(
            ["git", "cat-file", "blob", f"{commit}:{path}"],
            cwd=repo,
            capture_output=True,
            check=False,
        )
        if blob.returncode != 0:
            raise ViewerError(f"cannot read {path} at {commit[:7]}")
        try:
            files[rel] = blob.stdout.decode("utf-8")
        except UnicodeDecodeError as err:
            raise ViewerError(f"{path} is not UTF-8 text") from err
    if not config_found:
        raise ViewerError(f"{project}/{CONFIG_NAME} not found at {commit[:7]}")
    if not files:
        raise ViewerError(f"no {MODEL_SUFFIX} files in {project} at {commit[:7]}")
    return files


def workspace_json(files: dict[str, str]) -> str:
    """The static workspace: `{"files": {"<path>": "<text>"}}`, the shape of GET /api/workspace."""
    return json.dumps({"files": dict(sorted(files.items()))}, ensure_ascii=False, indent=1) + "\n"


def swap_in(new: Path, target: Path, attempts: int = 5) -> None:
    """viewer.swap_in, retried: on Windows a scanner can hold fresh files for a moment."""
    for attempt in range(attempts):
        try:
            viewer.swap_in(new, target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(1)


def assemble(
    *,
    repo: Path,
    ref: str,
    project: str,
    base: str,
    app: Path,
    out: Path,
    optional: bool = False,
    run: Runner = subprocess.run,
) -> None:
    viewer.check_base(base)
    viewer.check_pages_out(repo, out)
    if not app.is_dir():
        if optional:
            print(f"editor demo skipped: {app.as_posix()} not built (just editor-demo-app)")
            return
        raise ViewerError(f"{app.as_posix()} not found: run `just editor-demo-app` first")
    check_bundle(app, base)
    target = viewer.parse_ref(ref)
    commit = viewer.resolve_commit(repo, target, "origin", run)
    files = read_model_files(repo, commit, project, run)
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="work-", dir=out.parent))
    try:
        staged = work / "editor"
        shutil.copytree(app, staged)
        (staged / "workspace.json").write_bytes(workspace_json(files).encode("utf-8"))
        swap_in(staged, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"editor demo ({len(files)} files of {project} @ {commit[:7]}) -> {out.as_posix()}/")


def build_command(engine: str, base: str) -> list[str]:
    return [
        engine,
        "build",
        "-f",
        CONTAINERFILE,
        "--target",
        "demo",
        "--build-arg",
        f"DEMO_BASE={base}",
        "-t",
        IMAGE_TAG,
        ".",
    ]


def extract(engine: str, dest: Path, run: Runner) -> None:
    """Copy /demo out of the built image: create, cp, rm (the container is always removed)."""
    # A scratch image has no command; the container never runs, so any string will do.
    created = run([engine, "create", IMAGE_TAG, "/demo"], capture_output=True, check=False)
    container = created.stdout.decode().strip() if created.returncode == 0 else ""
    if not container:
        raise ViewerError(f"{engine} create failed for {IMAGE_TAG}")
    try:
        if run([engine, "cp", f"{container}:/demo/.", str(dest)], check=False).returncode != 0:
            raise ViewerError(f"{engine} cp failed: could not copy /demo out of {IMAGE_TAG}")
    finally:
        run([engine, "rm", "-f", container], capture_output=True, check=False)


def build_app(
    *, repo: Path, base: str, engine: str, out: Path, run: Runner = subprocess.run
) -> None:
    viewer.check_base(base)
    viewer.check_pages_out(repo, out)
    if run(build_command(engine, base), cwd=repo, check=False).returncode != 0:
        raise ViewerError(f"{engine} build of the demo failed; previous app kept")
    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="work-", dir=out.parent))
    try:
        staged = work / "app"
        staged.mkdir()
        extract(engine, staged, run)
        check_bundle(staged, base)
        swap_in(staged, out)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(f"editor demo app ({base}) -> {out.as_posix()}/")


def main(argv: Sequence[str] | None = None, run: Runner = subprocess.run) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    engine_default = os.environ.get("CONTAINER_ENGINE", "podman")
    app_cmd = sub.add_parser("app", help="build the static app with the container engine")
    app_cmd.add_argument("--base", required=True, help="URL path of the demo, e.g. /name/editor/")
    app_cmd.add_argument("--out", default=DEFAULT_APP)
    app_cmd.add_argument("--engine", default=engine_default)
    app_cmd.add_argument("--repo", default=str(REPO), help=argparse.SUPPRESS)
    asm = sub.add_parser("assemble", help="add workspace.json to the app and put it into --out")
    asm.add_argument("--base", required=True, help="URL path of the demo, e.g. /name/editor/")
    asm.add_argument("--ref", default="main", help="main, pr/<n>, a branch or HEAD")
    asm.add_argument("--project", default=os.environ.get("MODEL", "examples/shop"))
    asm.add_argument("--app", default=DEFAULT_APP)
    asm.add_argument("--out", default=DEFAULT_OUT)
    asm.add_argument("--optional", action="store_true", help="skip quietly if the app is not built")
    asm.add_argument("--repo", default=str(REPO), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    repo = Path(args.repo)

    def inside(path: str) -> Path:
        return Path(path) if Path(path).is_absolute() else repo / path

    try:
        if args.command == "app":
            build_app(repo=repo, base=args.base, engine=args.engine, out=inside(args.out), run=run)
        else:
            assemble(
                repo=repo,
                ref=args.ref,
                project=args.project.replace("\\", "/").strip("/"),
                base=args.base,
                app=inside(args.app),
                out=inside(args.out),
                optional=args.optional,
                run=run,
            )
    except ViewerError as err:
        print(str(err), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
