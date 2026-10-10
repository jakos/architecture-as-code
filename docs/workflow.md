# Workflow (draft)

Status: **draft**. A box marked ✅ exists in the repo; ⏳ is designed but not built yet.
Research on the technical flow, the browser editor and the branch/PR lifecycle:
[research/structurizr-workflows.md](research/structurizr-workflows.md).
LikeC4 compared with this workflow: [research/likec4-comparison.md](research/likec4-comparison.md)
([ADR 0005](decisions/0005-trial-likec4-for-the-editor-path.md), accepted: a trial of LikeC4 for
the editor path). The local PoC of Flow B1 in both tools, with measurements:
[research/likec4-trial-poc.md](research/likec4-trial-poc.md).

```
            ┌───────────── Flow A: edit in repo ─────────────┐
 you/Claude ─► *.dsl ─► just check ─► branch ─► PR ─► CI: just check ─► merge ─► main
                 ▲                                                         │
 Flow B1 ────────┘ (editor container: browser editor + live render,        ▼
                    "submit" = commit to branch + gh pr create)      deploy jobs:
                                                                     1. publish static site         ✅ local / ⏳ CI
                                                                     2. drift check vs Kubernetes   ⏳
                                                                     3. (later) generate objects    ⏳
```

## Flow A: edit models directly in the repo ✅

1. `just up` starts Structurizr in `local` mode on http://localhost:8080 with
   `examples/shop` mounted (`WORKSPACE=examples/other just up` for another workspace).
2. Edit `workspace.dsl` in your editor, refresh the browser to see it re-rendered.
3. `just check` validates every workspace (also runs on pre-push and in CI).
4. Branch, commit, PR as usual.

## Flow B1: editor in a container that opens PRs ⏳ (local PoC built, no PR opened yet)

Goal: someone without a local checkout edits the model in a browser and the result
arrives as a PR. Structurizr itself cannot write DSL back to git, so the container wraps it:

- A **fresh clone** of the repo inside the container (never the user's working copy),
  checked out on a new branch `model/<user>/<date>-<slug>`.
- A browser editor (code-server) on the clone, plus `structurizr local` on the same
  directory for live rendering.
- A `submit` command: `structurizr validate` → commit → push the branch →
  `gh pr create`. Auth via a fine-grained GitHub token with only `contents:write` and
  `pull_requests:write` on this repo, passed as an env var, never baked into the image.
- It can never push to `main`: the script refuses, and branch protection enforces it.

Local PoC (✅ built and run locally; results in
[research/likec4-trial-poc.md](research/likec4-trial-poc.md)): `just editor-build`, then
`just poc-remote` (a local bare repo `build/poc-remote.git` stands in for GitHub), then
`just editor-up TOOL=structurizr` or `just editor-up TOOL=likec4` (needs `PASSWORD`,
`MODEL_USER` and `MODEL_SLUG`, see `.env.example`). code-server is on http://127.0.0.1:8090
(Structurizr, render on 8091) or http://127.0.0.1:8092 (LikeC4, dev server on 8093).
`submit` (`tools/submit.py`) validates, commits the model directory, sends the `model/*`
branch to the bare repo and prints the `gh pr create` command; it does not run it.
`just editor-down` stops both. The LikeC4 variant edits `trial/likec4/shop`
([README](../trial/likec4/README.md), checked with `just trial-check`).

The two earlier open questions are answered in the
[research draft](research/structurizr-workflows.md#open-questions-from-flow-b1): one
container per editing session, and `playground` cannot replace code-server (it cannot
read or write files in a clone). The research adds two details to the design above:
set `STRUCTURIZR_EDITABLE=false` in the editor container (layout changes would not reach
the PR anyway), and enforce "no push to `main`" with branch protection as well as the script.

## Deploy 1: publish a browsable site ✅ locally, ⏳ CI

`just site` exports every workspace with `structurizr export -f static` into
`build/site/<dir-name>/` plus an index page, and serves it on http://localhost:8081.
This is the same diagram viewer as the server (zoom, navigation between views, docs),
read-only, as plain files. Next: a CI job on merge to `main` that publishes `build/site`
to GitHub Pages (private Pages needs GitHub Enterprise Cloud; otherwise another host).

The paid Structurizr server is not used; see ADR 0004 for when to reconsider.

## Deploy 2: drift check against Kubernetes ⏳ (chosen first, see ADR 0003)

The model does not create anything yet. A job compares the deployment model with what is
actually running and reports differences in both directions:

- **In the model, not in the cluster**: a `containerInstance` whose `kubernetes.*`
  properties point to a workload that does not exist.
- **In the cluster, not in the model**: a workload in a namespace the model covers, with
  no matching `containerInstance`.

How: `structurizr export -f json` → Python reads the `kubernetes.*` properties (see
[conventions](conventions.md)) → compares with `kubectl get deploy,sts -o json`. Runs
read-only. Locally against a `kind` cluster (Kubernetes in containers), later on a
schedule against real clusters with a read-only service account.

## Deploy 3 (later): create objects from new components ⏳

When someone adds a new container to the model, a job scaffolds its Kubernetes objects
(namespace, Deployment, Service) from the same `kubernetes.*` properties and opens a PR
in the infrastructure repo. It does not apply anything directly; the infra repo's own
pipeline stays the only thing that changes a cluster. The drift check from Deploy 2
then confirms the result.
