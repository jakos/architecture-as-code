# 0004: Browse the architecture as a static site, not the Structurizr server

Date: 2026-10-09 · Status: superseded by [0006](0006-likec4-is-the-tool-of-record.md)

## Context

"Deploying" includes showing the current architecture in an easy-to-explore way. The
prebuilt Structurizr `server` mode exits on start without a `structurizr.license`
("No license found"). Licenses start at about £300/month for 1–20 users; a 14-day trial
exists. The open core is free but must be built from source. `local` mode is free but
serves one workspace and is meant for authoring.

## Decision

Publish `structurizr export -f static` output: the same interactive viewer as plain
files, one site per workspace plus an index. Served locally by nginx (`just site`), and
by GitHub Pages (or another static host) from CI.

## Consequences

- Free, no server to run, nothing writable to drift from git.
- No server-side search across workspaces, no per-user auth, no version history in the
  UI (git has the history). If those become necessary, compare a license with building
  the open core.

Sources: https://docs.structurizr.com/server/pricing, https://docs.structurizr.com/server
