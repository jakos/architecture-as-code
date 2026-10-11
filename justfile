set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set dotenv-load

engine := env("CONTAINER_ENGINE", "podman")
editor_compose := engine + " compose -f docker/compose.editor.yml"
likec4_image := "docker.io/likec4/likec4:1.59.4"
nginx_image := "docker.io/library/nginx:1.29.4-alpine"

# Default variant for `editor-up`: likec4 (code-server) or likec4-web. Documented form: `just editor-up TOOL=likec4`
TOOL := "likec4"

# Model project served by `up` and `site`
MODEL := env("MODEL", "examples/shop")

# The gate: Python tooling + every LikeC4 project must validate and be formatted
check:
    uv run --locked ruff format --check .
    uv run --locked ruff check .
    uv run --locked pytest -q
    uv run --locked python tools/validate_models.py

# Validate (and format-check) only the LikeC4 projects (faster when you did not touch tools/)
validate *roots:
    uv run --locked python tools/validate_models.py {{roots}}

# Live-rendering `likec4 start` on http://127.0.0.1:8080 (MODEL=examples/shop by default)
up:
    {{engine}} rm -f aac-likec4
    {{engine}} run -d --name aac-likec4 -p 127.0.0.1:8080:5173 -p 127.0.0.1:24678:24678 -e CHOKIDAR_USEPOLLING=true -v "./{{MODEL}}:/data" {{likec4_image}} start --listen 0.0.0.0 --port 5173 --no-use-dot

# Build the static site of MODEL into build/site and serve it on http://127.0.0.1:8081
site:
    uv run --locked python -c "import pathlib; pathlib.Path('build/site').mkdir(parents=True, exist_ok=True)"
    {{engine}} run --rm -v "./{{MODEL}}:/data:ro" -v "./build/site:/out" {{likec4_image}} build -o /out --use-hash-history
    {{engine}} rm -f aac-site
    {{engine}} run -d --name aac-site -p 127.0.0.1:8081:80 -v "./build/site:/usr/share/nginx/html:ro" {{nginx_image}}

# Stop and remove the containers of `up` and `site` (fine if they are not running)
down:
    {{engine}} rm -f aac-likec4 aac-site

# B1 editor PoC: build the editor images (first build pulls code-server, node and LikeC4)
editor-build:
    {{engine}} build -f docker/editor/likec4/Containerfile -t localhost/aac-editor-likec4:poc .
    {{engine}} build -f docker/editor/likec4-web/Containerfile -t localhost/aac-editor-likec4-web:poc .

# LikeC4 playground built from source at tag v1.59.4 (separate: needs GitHub and npm, takes minutes)
playground-build:
    {{engine}} build -f docker/editor/likec4-playground/Containerfile -t localhost/aac-likec4-playground:v1.59.4 .

# Start the self-built playground on http://127.0.0.1:8096 (no clone, no password)
playground-up:
    {{editor_compose}} --profile likec4-playground up -d likec4-playground

# B1 editor PoC (Podman only): snapshot the working tree and seed the local bare remote build/poc-remote.git
poc-remote:
    uv run --locked python tools/poc_remote.py snapshot . build/poc-seed
    {{engine}} run --rm --userns=keep-id:uid=1000,gid=1000 -v "./build:/build" --entrypoint python3 localhost/aac-editor-likec4:poc /usr/local/lib/poc/poc_remote.py seed /build/poc-seed /build/poc-remote.git

# B1 editor PoC: start one editor on a fresh clone of build/poc-remote.git. Podman only (userns keep-id).
# Usage: `just editor-up TOOL=likec4` or `TOOL=likec4-web` for the editing service (also `just editor-up likec4`, `just TOOL=likec4 editor-up`).
# Needs PASSWORD, MODEL_USER, MODEL_SLUG in the environment or .env (see .env.example).
editor-up tool=TOOL:
    uv run --locked python -c "import os, shutil, pathlib; p = pathlib.Path('build/editor/{{trim_start_match(tool, 'TOOL=')}}/model'); shutil.rmtree(p, onexc=lambda f, q, e: (os.chmod(q, 0o700), f(q))) if p.exists() else None; p.mkdir(parents=True)"
    {{editor_compose}} --profile {{trim_start_match(tool, 'TOOL=')}} up -d --force-recreate

editor-down:
    {{editor_compose}} --profile likec4 --profile likec4-web --profile likec4-playground down
