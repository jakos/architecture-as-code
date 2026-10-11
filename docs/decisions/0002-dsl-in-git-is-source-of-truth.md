# 0002: The DSL in git is the single source of truth

Date: 2026-10-09 · Status: accepted

Amended by [0005](0005-trial-likec4-for-the-editor-path.md) for the LikeC4 trial editor only.

Amended by [0006](0006-likec4-is-the-tool-of-record.md): the model files are `.c4` files, read ".dsl" in this ADR as ".c4".

## Context

There are two ways to edit: directly in the repo (Flow A) and through a browser editor
in a container (Flow B). Structurizr's UI editing can store model state outside git
(server workspaces), which drifts from the DSL.

## Decision

Every model change is a change to `.dsl` files that arrives through a PR. The browser
editor (Flow B1) is a wrapper around a git clone: Structurizr `local` renders the DSL, a
submit step commits and opens a PR. The browsable view is a static export that CI
regenerates on every merge (ADR 0004).

Rejected: B2 (edit in Structurizr server, export to git), because two writable copies
drift. B3 (devcontainer/Codespace only) is still possible as an extra, but it does not
serve people who do not use git.

## Consequences

- Layout lives in the DSL (`autolayout`) by default. `local` mode writes `workspace.json`
  on every load, so it is gitignored; a hand-made layout worth keeping is committed with
  `git add -f`.
