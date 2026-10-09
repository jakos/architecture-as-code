# Workflow (draft)

Status: **draft**. A box marked ✅ exists in the repo; ⏳ is designed but not built yet.

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

## Flow B1: editor in a container that opens PRs ⏳

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

Open questions: one container per editing session or long-lived per person? Is the
`playground` mode of the Structurizr image a usable browser DSL editor in place of
code-server?

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
