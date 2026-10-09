# architecture-as-code

Tooling and workflow for keeping a system's architecture as a C4 model in Structurizr DSL,
in git: validating it, editing it (directly or through a browser editor in a container
that opens PRs), publishing it as a browsable site, and checking the deployment model
against Kubernetes. Real workspaces will live in `workspaces/`; `examples/` holds example
workspaces for trying out the tooling. Separate from `repos/mind-map` (the Markdown
knowledge base). Status: early draft; `docs/workflow.md` marks what exists and what is planned.

## Constraints that are not obvious from the code

- Structurizr is the consolidated "vNext" tool: one image `docker.io/structurizr/structurizr`
  with modes `local` / `server` / `validate` / `export` / `push`. The old `structurizr/lite`,
  `structurizr/cli` and `structurizr/onpremises` are end-of-life: do not use them. (ADR 0001)
- The prebuilt Structurizr `server` needs a paid license (from ~£300/month; open core is
  free only if built from source). Browsing uses the free `export -f static` site. (ADR 0004)
- Structurizr cannot write model changes back to DSL or git. Anything "edit in the UI →
  PR" has to be built around a git clone. (ADR 0002)
- Structurizr has no model → infrastructure feature. The `kubernetes.*` properties in
  `docs/conventions.md` are our own contract, read by our own tools.
- Local container engine is **Podman** (no Docker on this machine); CI uses Docker.
  Recipes read `CONTAINER_ENGINE` (default `podman`).
- In Git Bash, `podman run -v` paths get mangled: set `MSYS_NO_PATHCONV=1` or call
  through `just` / Python.

## Non-negotiables

**Assumed:** proposed in the bootstrap session, not yet confirmed by the owner.

1. Never apply anything to a real cluster or cloud account from this repo. The drift check
   is read-only; future object generation opens PRs in the infra repo, it does not apply.
2. The editor container never pushes to `main`, only to `model/*` branches followed by a PR.
3. No credentials in DSL, compose files, images or the repo. Tokens come from env vars;
   `.env` is gitignored.
4. Do not rename a `kubernetes.*` property or an element identifier used by tooling without
   updating the tooling and every workspace in the same change.

## Commands

```
just check        # the gate: ruff format/lint, pytest, structurizr validate on all workspaces
just validate     # only the DSL
just up           # structurizr local on :8080 (WORKSPACE=examples/shop by default)
just site         # export static site to build/site, serve on :8081
just down
```

## Conventions

- Structurizr image tag is pinned in `tools/validate_workspaces.py` and `docker/compose.yml`;
  bump both together.
- One workspace per directory, file named `workspace.dsl` (validator discovers by name).
- Decisions go in `docs/decisions/NNNN-*.md` with date, context, decision, consequences.
- Helper logic is Python under `tools/` run via `uv run`, not shell scripts (Windows + CI).

## Layout

| Path | What |
| --- | --- |
| `examples/` | Example workspaces, safe to change |
| `workspaces/` | Real workspaces (not yet created) |
| `tools/` | Python helpers + `tools/tests/` |
| `docker/compose.yml` | Local Structurizr `local` + static site preview |
| `docs/` | Workflow, conventions, ADRs |
