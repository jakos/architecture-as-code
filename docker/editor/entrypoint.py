"""Entrypoint of the B1 editor containers (PoC): fresh clone, model/* branch, renderer, editor.

Environment (nothing is baked into the image):
  REPO_URL        what to clone (the PoC passes the local bare remote)
  MODEL_USER      who is editing; used in the branch name and as the git author
  MODEL_SLUG      short description of the change; used in the branch name
  RENDERER        structurizr | likec4
  MODEL_PATH      model directory inside the clone (examples/shop or trial/likec4/shop)
  PASSWORD        code-server login password
  SPARSE_EXCLUDE  optional, space-separated paths left out of the checkout
  MODEL_DIR       clone location (default /home/coder/model, a bind mount)

Stdlib only; runs on the Python 3 shipped in the images.
"""

import datetime
import os
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

CODE_SERVER_PORT = 8080
RENDER_PORT = 8081  # structurizr local; likec4 start uses 5173 and is mapped by compose
LIKEC4_PORT = 5173
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
USER_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class SetupError(Exception):
    pass


def require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name, "").strip()
    if not value:
        raise SetupError(f"{name} is not set")
    return value


def branch_name(user: str, slug: str, today: datetime.date) -> str:
    if not USER_RE.match(user):
        raise SetupError(f"MODEL_USER '{user}' must be lowercase letters, digits, . _ -")
    if not SLUG_RE.match(slug):
        raise SetupError(f"MODEL_SLUG '{slug}' must be lowercase letters, digits, -")
    return f"model/{user}/{today.isoformat()}-{slug}"


def sparse_patterns(exclude: str) -> list[str]:
    """Non-cone sparse-checkout patterns: everything except the listed paths."""
    return ["/*", *[f"!/{p.strip('/')}" for p in exclude.split()]]


def git(*args: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise SetupError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def prepare_clone(env: Mapping[str, str], today: datetime.date) -> tuple[Path, str]:
    repo_url = require(env, "REPO_URL")
    user = require(env, "MODEL_USER")
    branch = branch_name(user, require(env, "MODEL_SLUG"), today)
    model_dir = Path(env.get("MODEL_DIR", "/home/coder/model"))
    model_dir.mkdir(parents=True, exist_ok=True)
    if any(model_dir.iterdir()):
        raise SetupError(f"{model_dir} is not empty: every session starts from a fresh clone")

    git("config", "--global", "--add", "safe.directory", "*")
    git("clone", "--no-checkout", repo_url, str(model_dir))
    exclude = env.get("SPARSE_EXCLUDE", "").strip()
    if exclude:
        git("sparse-checkout", "init", "--no-cone", cwd=model_dir)
        git("sparse-checkout", "set", "--no-cone", *sparse_patterns(exclude), cwd=model_dir)
    git("checkout", "-b", branch, "origin/main", cwd=model_dir)
    git("config", "core.fileMode", "false", cwd=model_dir)  # Windows-host bind mounts
    git("config", "user.name", user, cwd=model_dir)
    git("config", "user.email", f"{user}@example.invalid", cwd=model_dir)
    current = git("branch", "--show-current", cwd=model_dir)
    if current == "main" or not current.startswith("model/"):
        raise SetupError(f"clone is on '{current}', expected a model/* branch")
    return model_dir, branch


def renderer_command(renderer: str, workdir: Path) -> tuple[list[str], dict[str, str]]:
    if renderer == "structurizr":
        cmd = ["structurizr", "local", str(workdir)]  # local takes its data dir as an argument
        extra = {
            "PORT": str(RENDER_PORT),
            "STRUCTURIZR_EDITABLE": "false",
            "STRUCTURIZR_AUTOREFRESHINTERVAL": "2000",
        }
        return cmd, extra
    if renderer == "likec4":
        cmd = [
            "likec4", "start", "--listen", "0.0.0.0", "--port", str(LIKEC4_PORT), "--no-use-dot",
        ]  # fmt: skip
        return cmd, {"CHOKIDAR_USEPOLLING": "true"}
    raise SetupError(f"RENDERER '{renderer}' must be structurizr or likec4")


def main() -> int:
    env = os.environ
    try:
        require(env, "PASSWORD")
        renderer = require(env, "RENDERER")
        model_path = require(env, "MODEL_PATH")
        if renderer not in ("structurizr", "likec4"):
            raise SetupError(f"RENDERER '{renderer}' must be structurizr or likec4")
        model_dir, branch = prepare_clone(env, datetime.date.today())
    except SetupError as err:
        print(f"entrypoint: {err}", file=sys.stderr)
        return 1

    workdir = model_dir / model_path
    if not workdir.is_dir():
        print(f"entrypoint: {workdir} does not exist in the clone", file=sys.stderr)
        return 1
    cmd, extra = renderer_command(renderer, workdir)
    print(f"editor ready on branch {branch}; rendering {model_path} with {renderer}", flush=True)
    renderer_env = {k: v for k, v in env.items() if k != "PASSWORD"}  # only code-server needs it
    subprocess.Popen(cmd, cwd=workdir, env={**renderer_env, **extra})
    os.execvp(
        "code-server",
        [
            "code-server", "--bind-addr", f"0.0.0.0:{CODE_SERVER_PORT}", "--auth", "password",
            "--disable-telemetry", "--disable-update-check", str(model_dir),
        ],
    )  # fmt: skip


if __name__ == "__main__":
    sys.exit(main())
