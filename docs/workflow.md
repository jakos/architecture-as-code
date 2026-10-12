# Workflow (draft)

Status: **draft**. A box marked ✅ exists in the repo; ⏳ is designed but not built yet.
The tool is LikeC4 ([ADR 0006](decisions/0006-likec4-is-the-tool-of-record.md)). History,
written while Structurizr was still in use: research on the technical flow and the branch/PR
lifecycle ([research/structurizr-workflows.md](research/structurizr-workflows.md)), LikeC4
compared with that workflow ([research/likec4-comparison.md](research/likec4-comparison.md)),
and the local PoC of Flow B1 with measurements
([research/likec4-trial-poc.md](research/likec4-trial-poc.md)).

```
            ┌───────────── Flow A: edit in repo ─────────────┐
 you/Claude ─► *.c4 ─► just check ─► branch ─► PR ─► CI: just check ─► merge ─► main
                 ▲                                                         │
 Flow B1 ────────┘ (editor container: browser editor + live render,        ▼
                    "submit" = commit to branch + gh pr create)      deploy jobs:
                                                                     1. publish static site         ✅ local / ⏳ CI
                                                                     2. drift check vs Kubernetes   ⏳
                                                                     3. (later) generate objects    ⏳
```

## Flow A: edit models directly in the repo ✅

1. `just up` starts `likec4 start` on http://127.0.0.1:8080 with `examples/shop` mounted
   (`MODEL=workspaces/other just up` for another project).
2. Edit the `.c4` files in your editor; the browser re-renders them.
3. `just check` validates and format-checks every LikeC4 project (also runs on pre-push and
   in CI).
4. Branch, commit, PR as usual.

## Flow B1: editor in a container that opens PRs ⏳ (local PoC built, no PR opened yet)

Goal: someone without a local checkout edits the model in a browser and the result
arrives as a PR. LikeC4 cannot write model changes back to git, so the container wraps it:

- A **fresh clone** of the repo inside the container (never the user's working copy),
  checked out on a new branch `model/<user>/<date>-<slug>`.
- A browser editor (code-server) on the clone, plus `likec4 start` on the model directory
  for live rendering.
- A `submit` command: `likec4 validate` and `likec4 format --check` → commit → push the
  branch → `gh pr create`. Auth via a fine-grained GitHub token with only `contents:write`
  and `pull_requests:write` on this repo, passed as an env var, never baked into the image.
- It can never push to `main`: the script refuses, and branch protection enforces it.

Local PoC (✅ built and run locally; results in
[research/likec4-trial-poc.md](research/likec4-trial-poc.md), written when both tools were
compared): `just editor-build`, then `just poc-remote` (a local bare repo
`build/poc-remote.git` stands in for GitHub), then `just editor-up TOOL=likec4` (needs
`PASSWORD`, `MODEL_USER` and `MODEL_SLUG`, see `.env.example`). code-server is on
http://127.0.0.1:8092, the `likec4 start` dev server on http://127.0.0.1:8093. `submit`
(`tools/submit.py`) validates, commits the `.c4` files of the model directory (layout `.snap`
files are skipped and listed, [ADR 0008](decisions/0008-layout-snap-policy.md)), sends the
`model/*` branch to the bare repo and prints the `gh pr create` command; it does not run it. `just editor-down` stops
it. The editor works on `examples/shop` (`MODEL_PATH` in the Containerfiles).

Editing service (✅ local PoC, no code-server): `just editor-up likec4-web` serves a page with
a text editor and the live LikeC4 diagram, on http://127.0.0.1:8094 (password) with the
diagram on http://127.0.0.1:8095. It writes the `.c4` files of the fresh clone and sends them
through the same `submit`; it is chosen with `EDITOR_UI=web` (`RENDER_URL` and `HMR_PORT` are
set by `docker/compose.editor.yml`). Details, measurements and open questions:
[research/likec4-web-editing.md](research/likec4-web-editing.md).

Model editor (✅ local PoC): the LikeC4 playground at tag `v1.59.4` plus our patch set, with a
file tree, save and autosave to the clone, Validate, Format and a Submit dialog
([ADR 0007](decisions/0007-model-editor-on-likec4-playground.md)). Build it with
`just model-editor-build` (needs GitHub and npm, takes minutes), then `just poc-remote` and
`just editor-up model-editor` (`PASSWORD`, `MODEL_USER`, `MODEL_SLUG`); it is on
http://127.0.0.1:8097 and `just editor-down` stops it. `just playground-patches-stat` shows how
much of the playground the patches change. Details, measurements and the upgrade trial:
[research/likec4-editor-image.md](research/likec4-editor-image.md); how to rebuild and upgrade:
`docker/editor/model-editor/README.md`. It replaces the textarea page (`likec4-web`), which
stays until a follow-up removes it.

"No push to `main`" is enforced by the script and, later, by branch protection.

## Deploy 1: publish a browsable site ✅ locally, ⏳ CI

`just site` runs `likec4 build` on `examples/shop` into `build/site` (with hash-history
navigation, so deep links work on a plain file server) and serves it on
http://127.0.0.1:8081. It is the same diagram viewer as `just up` (zoom, navigation between
views), read-only, as plain files. Next: a CI job on merge to `main` that publishes
`build/site` to GitHub Pages (private Pages needs GitHub Enterprise Cloud; otherwise another
host).

No server is run; see [ADR 0006](decisions/0006-likec4-is-the-tool-of-record.md).

## Deploy 2: drift check against Kubernetes ⏳ (chosen first, see ADR 0003)

The model does not create anything yet. A job compares the deployment model with what is
actually running and reports differences in both directions:

- **In the model, not in the cluster**: a deployment instance whose `kubernetes_*`
  metadata point to a workload that does not exist.
- **In the cluster, not in the model**: a workload in a namespace the model covers, with
  no matching deployment instance.

How: `likec4 export json` → Python reads the `kubernetes_*` metadata (see
[conventions](conventions.md)) → compares with `kubectl get deploy,sts -o json`. Runs
read-only. Locally against a `kind` cluster (Kubernetes in containers), later on a
schedule against real clusters with a read-only service account.

## Deploy 3 (later): create objects from new components ⏳

When someone adds a new container to the model, a job scaffolds its Kubernetes objects
(namespace, Deployment, Service) from the same `kubernetes_*` metadata and opens a PR
in the infrastructure repo. It does not apply anything directly; the infra repo's own
pipeline stays the only thing that changes a cluster. The drift check from Deploy 2
then confirms the result.
