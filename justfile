set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set dotenv-load

engine := env("CONTAINER_ENGINE", "podman")
compose := engine + " compose -f docker/compose.yml"
editor_compose := engine + " compose -f docker/compose.editor.yml"
likec4_image := "docker.io/likec4/likec4:1.59.4"

# Default tool for `editor-up`: structurizr or likec4. Documented form: `just editor-up TOOL=likec4`
TOOL := "structurizr"

# The gate: Python tooling + every Structurizr workspace must validate
check:
    uv run --locked ruff format --check .
    uv run --locked ruff check .
    uv run --locked pytest -q
    uv run --locked python tools/validate_workspaces.py

# Validate only the DSL (faster when you did not touch tools/)
validate *roots:
    uv run --locked python tools/validate_workspaces.py {{roots}}

# Live-rendering local Structurizr on http://localhost:8080 (WORKSPACE=examples/shop by default)
up:
    {{compose}} up -d structurizr-local

# Export all workspaces as a static site and serve it on http://localhost:8081
site:
    uv run --locked python tools/export_site.py
    {{compose}} --profile site up -d site

down:
    {{compose}} --profile site down

# LikeC4 trial port: validate and check formatting (own check, not part of `just check`; ADR 0005)
trial-check:
    {{engine}} run --rm -v "./trial/likec4/shop:/data:ro" {{likec4_image}} validate
    {{engine}} run --rm -v "./trial/likec4/shop:/data:ro" {{likec4_image}} format --check

# B1 editor PoC: build the editor images (first build pulls code-server, node and LikeC4)
editor-build:
    {{engine}} build -f docker/editor/structurizr/Containerfile -t localhost/aac-editor-structurizr:poc .
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
    {{engine}} run --rm --userns=keep-id:uid=1000,gid=1000 -v "./build:/build" --entrypoint python3 localhost/aac-editor-structurizr:poc /usr/local/lib/poc/poc_remote.py seed /build/poc-seed /build/poc-remote.git

# B1 editor PoC: start one editor on a fresh clone of build/poc-remote.git. Podman only (userns keep-id).
# Usage: `just editor-up TOOL=likec4` (or `likec4-web` for the editing service) (also `just editor-up likec4`, `just TOOL=likec4 editor-up`).
# Needs PASSWORD, MODEL_USER, MODEL_SLUG in the environment or .env (see .env.example).
editor-up tool=TOOL:
    uv run --locked python -c "import os, shutil, pathlib; p = pathlib.Path('build/editor/{{trim_start_match(tool, 'TOOL=')}}/model'); shutil.rmtree(p, onexc=lambda f, q, e: (os.chmod(q, 0o700), f(q))) if p.exists() else None; p.mkdir(parents=True)"
    {{editor_compose}} --profile {{trim_start_match(tool, 'TOOL=')}} up -d --force-recreate

editor-down:
    {{editor_compose}} --profile structurizr --profile likec4 --profile likec4-web --profile likec4-playground down
