# architecture-as-code

C4 architecture models in LikeC4, kept in git, with a workflow for editing, validating,
publishing and checking them against Kubernetes.

**Status:** draft. See [docs/workflow.md](docs/workflow.md) for the flows and what is built.

## Quick start

Needs: [uv](https://docs.astral.sh/uv/), [just](https://just.systems/), Podman or Docker.

```
uv sync
uv run prek install
just check                  # validate everything
just up                     # http://127.0.0.1:8080 renders examples/shop live
just site                   # http://127.0.0.1:8081 static site of examples/shop
just down                   # stop both
```

Using Docker instead of Podman: copy `.env.example` to `.env` and set `CONTAINER_ENGINE=docker`.

## Docs

- [Workflow](docs/workflow.md): edit in repo, browser editor → PR, deploy
- [ADR 0006](docs/decisions/0006-likec4-is-the-tool-of-record.md): LikeC4 is the tool of record
- [Conventions](docs/conventions.md): Kubernetes metadata keys, project layout
- [Decisions](docs/decisions/)
- History, written before the switch from Structurizr:
  - [Workflow research](docs/research/structurizr-workflows.md): options for the browser editor and the branch/PR lifecycle
  - [LikeC4 comparison](docs/research/likec4-comparison.md): LikeC4 compared with the Structurizr workflow
  - [LikeC4 trial PoC](docs/research/likec4-trial-poc.md): the browser-editor path built locally in both tools, with measurements
  - [LikeC4 web editing](docs/research/likec4-web-editing.md): the in-browser editing service
