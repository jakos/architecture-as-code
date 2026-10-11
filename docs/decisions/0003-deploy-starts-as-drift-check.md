# 0003: Deployment starts as a read-only drift check against Kubernetes

Date: 2026-10-09 · Status: accepted

Amended by [0006](0006-likec4-is-the-tool-of-record.md): the contract keys are `kubernetes_namespace`, `kubernetes_kind` and
`kubernetes_name` metadata keys instead of the dotted property names below.

## Context

"Deploying architecture" means two things: (1) people can browse the current
architecture, (2) jobs act on infrastructure based on the model. Structurizr has no
model-to-infrastructure feature, and C4 deployment models leave out most of what
infrastructure needs (resources, secrets, networking), so generating it fully from the
model would push infra detail into the DSL.

Options: generate infra from the model; check infra against the model (drift); have the
model trigger existing pipelines.

## Decision

Start with the drift check: read-only, against Kubernetes, prototyped on a local `kind`
cluster. The `kubernetes.*` properties (docs/conventions.md) are designed so that the
same data can later scaffold objects for newly added components. That step opens PRs in
the infrastructure repo and never applies anything to a cluster.

## Consequences

- No credentials with write access to any cluster are needed by this repo.
- Property names become a contract: renaming one is a breaking change.
