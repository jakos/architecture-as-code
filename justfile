set windows-shell := ["powershell.exe", "-NoLogo", "-Command"]
set dotenv-load

engine := env("CONTAINER_ENGINE", "podman")
compose := engine + " compose -f docker/compose.yml"

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
