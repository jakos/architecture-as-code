# architecture-as-code

C4 architecture models in Structurizr DSL, kept in git, with a workflow for editing,
validating, publishing and checking them against Kubernetes.

**Status:** draft. See [docs/workflow.md](docs/workflow.md) for the flows and what is built.

## Quick start

Needs: [uv](https://docs.astral.sh/uv/), [just](https://just.systems/), Podman or Docker.

```
uv sync
uv run prek install
just check                  # validate everything
just up                     # http://localhost:8080 renders examples/shop live
just site                   # http://localhost:8081 static site of all workspaces
```

Using Docker instead of Podman: copy `.env.example` to `.env` and set `CONTAINER_ENGINE=docker`.

## Docs

- [Workflow](docs/workflow.md): edit in repo, browser editor → PR, deploy
- [Workflow research](docs/research/structurizr-workflows.md): draft options for the browser editor and the branch/PR lifecycle
- [LikeC4 comparison](docs/research/likec4-comparison.md): draft comparison of LikeC4 with the Structurizr workflow, and a proposed trial
- [Conventions](docs/conventions.md): Kubernetes properties, layout
- [Decisions](docs/decisions/)
