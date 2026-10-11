"""Entrypoint of the B1 editor containers (PoC): fresh clone, model/* branch, renderer, editor.

Environment (nothing is baked into the image):
  REPO_URL        what to clone (the PoC passes the local bare remote)
  MODEL_USER      who is editing; used in the branch name and as the git author
  MODEL_SLUG      short description of the change; used in the branch name
  RENDERER        likec4
  MODEL_PATH      model directory inside the clone (for example examples/shop)
  PASSWORD        login password of the editor UI (code-server, or web_editor.py in web mode)
  EDITOR_UI       code-server (default) | web (tools/web_editor.py: text editor + live diagram)
  RENDER_URL      web mode: URL of the renderer as the browser reaches it (iframe source)
  HMR_PORT        fixed port of the dev server's HMR websocket (default: automatic)
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
LIKEC4_PORT = 5173  # `likec4 start`; compose maps it
EDITOR_UIS = ("code-server", "web")
WEB_EDITOR = "/usr/local/lib/poc/web_editor.py"
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


def renderer_command(
    renderer: str, workdir: Path, env: Mapping[str, str] | None = None
) -> tuple[list[str], dict[str, str]]:
    if renderer == "likec4":
        cmd = [
            "likec4", "start", "--listen", "0.0.0.0", "--port", str(LIKEC4_PORT), "--no-use-dot",
        ]  # fmt: skip
        hmr_port = (env or {}).get("HMR_PORT", "").strip()
        if hmr_port:
            cmd += ["--hmr-port", hmr_port]
        return cmd, {"CHOKIDAR_USEPOLLING": "true"}
    raise SetupError(f"RENDERER '{renderer}' must be likec4")


def editor_ui(env: Mapping[str, str]) -> str:
    ui = env.get("EDITOR_UI", "").strip() or "code-server"
    if ui not in EDITOR_UIS:
        raise SetupError(f"EDITOR_UI '{ui}' must be one of: {', '.join(EDITOR_UIS)}")
    return ui


def editor_command(env: Mapping[str, str], model_dir: Path) -> list[str]:
    """The command that replaces this process: code-server by default, or the web editor."""
    if editor_ui(env) == "code-server":
        return [
            "code-server", "--bind-addr", f"0.0.0.0:{CODE_SERVER_PORT}", "--auth", "password",
            "--disable-telemetry", "--disable-update-check", str(model_dir),
        ]  # fmt: skip
    return [
        "python3", WEB_EDITOR, "--repo", str(model_dir), "--path", require(env, "MODEL_PATH"),
        "--port", str(CODE_SERVER_PORT), "--render-url", require(env, "RENDER_URL"),
    ]  # fmt: skip


def renderer_env(env: Mapping[str, str], extra: Mapping[str, str]) -> dict[str, str]:
    """Environment of the renderer: the editor UI's PASSWORD is not passed on."""
    return {**{k: v for k, v in env.items() if k != "PASSWORD"}, **extra}


def main() -> int:
    env = os.environ
    try:
        require(env, "PASSWORD")
        renderer = require(env, "RENDERER")
        model_path = require(env, "MODEL_PATH")
        if renderer != "likec4":
            raise SetupError(f"RENDERER '{renderer}' must be likec4")
        editor_ui(env)
        model_dir, branch = prepare_clone(env, datetime.date.today())
        command = editor_command(env, model_dir)
    except SetupError as err:
        print(f"entrypoint: {err}", file=sys.stderr)
        return 1

    workdir = model_dir / model_path
    if not workdir.is_dir():
        print(f"entrypoint: {workdir} does not exist in the clone", file=sys.stderr)
        return 1
    cmd, extra = renderer_command(renderer, workdir, env)
    print(f"editor ready on branch {branch}; rendering {model_path} with {renderer}", flush=True)
    subprocess.Popen(cmd, cwd=workdir, env=renderer_env(env, extra))
    os.execvp(command[0], command)


if __name__ == "__main__":
    sys.exit(main())
