# architecture-as-code

Tooling and workflow for keeping a system's architecture as a C4 model in LikeC4, in git:
validating it, editing it (directly or through a browser editor in a container that opens
PRs), publishing it as a browsable site, and checking the deployment model against
Kubernetes. Real models will live in `workspaces/`; `examples/` holds example projects for
trying out the tooling. Separate from `repos/mind-map` (the Markdown knowledge base).
Status: early draft; `docs/workflow.md` marks what exists and what is planned.

## Constraints that are not obvious from the code

- LikeC4 is the tool (ADR 0006): one image `docker.io/likec4/likec4` runs validate, format,
  start, build and export. Structurizr was removed; do not reintroduce it without a new ADR.
- LikeC4 cannot write model changes back to the `.c4` files or git. Anything "edit in the
  UI → PR" has to be built around a git clone. (ADR 0002)
- LikeC4 metadata keys cannot contain a dot, hence `kubernetes_namespace`, `kubernetes_kind`
  and `kubernetes_name`.
- LikeC4 has no model → infrastructure feature. The `kubernetes_*` metadata keys in
  `docs/conventions.md` are our own contract, read by our own tools.
- Local container engine is **Podman** (no Docker on this machine); CI uses Docker.
  Recipes read `CONTAINER_ENGINE` (default `podman`).
- In Git Bash, `podman run -v` paths get mangled: set `MSYS_NO_PATHCONV=1` or call
  through `just` / Python.

## Non-negotiables

1. Never apply anything to a real cluster or cloud account from this repo. The drift check
   is read-only; future object generation opens PRs in the infra repo, it does not apply.
2. The editor container never pushes to `main`, only to `model/*` branches followed by a PR.
3. No credentials in model files, compose files, images or the repo. Tokens come from env
   vars; `.env` is gitignored.
4. Do not rename a `kubernetes_*` metadata key or an element identifier used by tooling
   without updating the tooling and every model in the same change.

## Commands

```
just check        # the gate: ruff format/lint, pytest, likec4 validate + format --check on all projects
just validate     # only the LikeC4 projects
just up           # likec4 start on :8080 (MODEL=examples/shop by default)
just site         # likec4 build to build/site, serve on :8081
just down         # stop up and site
```

## Conventions

- The LikeC4 version is pinned in `justfile` (`likec4_image`), `tools/validate_models.py`
  (`IMAGE`) and the three editor Containerfiles (npm package, VS Code extension, and in
  `docker/editor/model-editor` also the playground tag and its commit); bump all together.
- One project per directory, with a `likec4.config.json` (the validator discovers by that
  name). Layout inside: `shared/`, `teams/<domain>/`, `views/` (see `docs/conventions.md`).
- Decisions go in `docs/decisions/NNNN-*.md` with date, context, decision, consequences.
- Helper logic is Python under `tools/` run via `uv run`, not shell scripts (Windows + CI).

## Layout

| Path | What |
| --- | --- |
| `examples/` | Example LikeC4 projects, safe to change |
| `workspaces/` | Real models (not yet created) |
| `tools/` | Python helpers + `tools/tests/` |
| `docker/compose.editor.yml` | Editor PoC containers (Podman) |
| `.github/CODEOWNERS` | Folder ownership of the model layout |
| `docs/` | Workflow, conventions, ADRs |
