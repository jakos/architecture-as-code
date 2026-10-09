# 0001: Use the consolidated Structurizr image for everything

Date: 2026-10-09 · Status: accepted

## Context

Structurizr CLI, Lite and on-premises were consolidated into one tool, "vNext"
(`structurizr/structurizr`), with the modes `local`, `server`, `validate`, `export` and
`push`. The old images get no more updates. Structurizr Cloud shut down on 2026-09-30.

## Decision

One image, `docker.io/structurizr/structurizr`, pinned to a release tag (currently
`2026.09.19`), for validation, local authoring and static-site export. It runs in
containers (Podman locally, Docker in CI), so nobody needs Java.

## Consequences

- Upgrading Structurizr means changing the tag in `tools/validate_workspaces.py` and
  `docker/compose.yml` together, as its own PR that passes `just check`.
- There is no SaaS option any more; see ADR 0004 for how viewing works.

Sources: https://www.patreon.com/Structurizr/posts/introducing-146923136,
https://hub.docker.com/r/structurizr/structurizr
