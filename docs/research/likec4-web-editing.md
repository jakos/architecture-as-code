# LikeC4 in-browser editing: playground, layout files and a local editing service

Status: measurements from one machine and one assistant, 2026-10-10. Indicative, not a
benchmark. Follows [likec4-trial-poc.md](likec4-trial-poc.md) after the owner tested its editor
and asked three things. The owner decides after reading this; nothing here changes
[ADR 0005](../decisions/0005-trial-likec4-for-the-editor-path.md).

Scope (owner edit, 2026-10-10): **editing only**, on the local setup. Hosted git providers,
how the model reaches a hosted container and a branch-selectable viewer are deferred (see
[Deferred to a later task](#deferred-to-a-later-task)).

Labels: **verified locally** (with the command), **from source at v1.59.4** (LikeC4 repo, tag
`v1.59.4`, commit `33dbc2d34c399a99daf96e92fc28fe5d280a7fd5`, read in a container clone),
**from docs**, **AI stand-in, not a real non-technical user** (headless Chrome driven by Playwright, run by
the orchestrator session on 2026-10-10; a throwaway password, deleted afterwards). Every
browser result below carries that label; no real person tried the page.

## Answers to the owner's three points

### Owner feedback 1: the layout-edit `.snap` file

- **What it is, from source at v1.59.4**
  (`packages/language-server/src/filesystem/LikeC4ManualLayouts.ts`): a manual layout is one
  file per view, named `<viewId>.likec4.snap`, in `.likec4/` inside the project folder (the
  directory can be changed with `manualLayouts.outDir` in the project config). The language
  server scans that directory for files ending in `.likec4.snap` and reads them with JSON5.
- **Does `submit` commit it?** By how `submit` is written, yes: `tools/submit.py` runs
  `git add -- <model dir>` and `git commit -- <model dir>`, the repository has no ignore rule for
  `.likec4/` (`.gitignore` ignores `build/`, not `.likec4/`), so a `.snap` file under
  `trial/likec4/shop/.likec4/` goes into the commit. **Measured (AI stand-in, not a
  real non-technical user):** in `likec4 start` on 8095, `/view/Containers/`, the padlock "Edit"
  button, dragging "Order API" by (+200, +120) px wrote an untracked
  `trial/likec4/shop/.likec4/Containers.likec4.snap` (`git status --porcelain
  --untracked-files=all`); `model.c4` was unchanged. After a reload the node stayed at the new
  position. `likec4 validate` accepts the file (VALID). Submitted through the editing page, the
  bare remote got `955ef78 Move Order API in the Containers view` with
  `trial/likec4/shop/.likec4/Containers.likec4.snap | 586 +++`. So **`submit` does commit layout
  snapshots**: a drag becomes a 586-line generated file in the PR. The owner's earlier manual
  test found the same on 8093: `LocalDeployment.likec4.snap`, 4190 bytes, `_stage: 'layouted'`,
  node positions; the owner "saw no change" because `model.c4` did not change.
- **What this means for the owner**: dragging an element in the dev server's "Edit" mode writes a
  file in the clone that is not a `.c4` file. If it is committed, the PR contains a layout
  change next to (or instead of) a model change. `submit` was **not changed** (owner decision):
  **finding for the owner, not a decision:** should layout snapshots be committed (kept as
  intended layout, reviewed like model text) or ignored (gitignore `.likec4/`, or not add them in
  `submit`)? Today they are committed without anyone choosing it. The editing service below writes only `.c4` files itself, but it cannot stop the
  dev server on port 8095 from writing `.snap` files into the same clone.

### Owner feedback 2: is the playground a separate mode of the tool?

- **No CLI mode. Verified locally**: `podman run --rm docker.io/likec4/likec4:1.59.4 --help`
  lists `start`, `build`, `gen`, `export`, `format`, `preview`, `publish` (LikeC4 Cloud, SaaS,
  not used here), `sync`, `validate`, `mcp`, `lsp`. The npm package `likec4@1.59.4` ships no
  playground and no Monaco editor.
- **It is a separate app, from source at v1.59.4**: `apps/playground` in the LikeC4 monorepo is
  "Sources of playground.likec4.dev", a Cloudflare Worker (`wrangler.jsonc`: KV namespace,
  GitHub OAuth variables, route `playground.likec4.dev`) serving a React single-page app with a
  Monaco editor and the language server in a Web Worker.
- **Where edits live, from source** (`apps/playground/src/state/persistence.ts`): in the
  browser's `localStorage` under `likec4:workspace:<id>` (built-in examples use
  `sessionStorage`). No file in a clone is read or written. The only "save" paths found are the
  server-side **share** feature (`worker/api.share.ts`, stored in the Worker's KV; needs the
  Worker and GitHub login) and a `.drawio` download from the diagram context menu. No download
  of the `.c4` text was found.
- **Network calls, from source**: `/api/*`, `/auth/*`, `/share/*` on its own origin (the Worker);
  fonts from `cdn.jsdelivr.net` (`src/font-fira-code.css`, `@latest`); links to likec4.dev and
  GitHub. No analytics code was found by `grep` for common names. Not observed in a browser.
- **Self-hosting**: **built and served locally** (**verified locally**).
  `docker/editor/likec4-playground/Containerfile` clones tag `v1.59.4` (commit `33dbc2d`), runs
  `pnpm install --frozen-lockfile --filter '@likec4/playground...'` (23 s in a first manual run)
  and `turbo run build` (72 s, 15 tasks), and serves `apps/playground/dist/client` with
  `nginx:1.29.4-alpine` (83 MB image `localhost/aac-likec4-playground:v1.59.4`; the full
  `just playground-build` took 6 min 47 s). `just playground-up` serves it on
  `http://127.0.0.1:8096`: `curl` returns 200 for `/` and for a deep link (`/w/abc`, SPA
  fallback). It is the static app only: the Worker is not built, so `/api/*`, `/auth/*` and
  `/share/*` answer with the HTML page, and share links and login cannot work.
  **In a browser (AI stand-in, not a real non-technical user):** `/` redirects to
  `/w/tutorial/index/` ("LikeC4 Playground"): Monaco editor (`tutorial.c4`) on the left, live
  diagram on the right, header with Share, Playgrounds, Docs, GitHub, "Login with GitHub"
  (Share and Login cannot work without the Worker). Replacing a description with Monaco's
  find/replace showed in the diagram after **0.49, 0.54 and 0.52 s** (no reload, no save step).
  Besides 127.0.0.1:8096 the page requested only `cdn.jsdelivr.net` (fonts); no request failed.
  Storage: `localStorage` holds `likec4:workspaces` (`[]`) and `notation-webview-collapsed`;
  `sessionStorage` holds `likec4:workspace:tutorial` and a panel-size key; IndexedDB is empty. So
  edits to the built-in tutorial are in **sessionStorage**: per tab, gone when the tab closes
  (this corrects the source reading above, which named `localStorage` for user-created
  workspaces; examples use `sessionStorage`). After a reload one run still showed the edited text
  and a second run did not, so persistence is inconsistent: treat it as not durable. There is no
  save or download of `.c4` in the UI. The playground is a scratchpad: text gets into the repo by
  copying it out by hand, or through a service like the page on 8094.

### Owner feedback 3: how are edits saved?

| Where you edit | Where the text lives | Reaches git? | Second writable copy that can drift? |
| --- | --- | --- | --- |
| (a) Playground (playground.likec4.dev or self-built), **from source** | browser `localStorage`; optional share link in the Worker's KV | no: no write-back to a clone, no download of the `.c4` text found | **yes**: a copy in one browser, separate from git. Someone must paste it back |
| (b) `likec4 start` layout "Edit" mode (port 8093 or 8095) | `.likec4/<view>.likec4.snap` files in the clone, **from source** | only through `submit`, which commits the whole model directory | no, it is the clone, but it adds non-`.c4` files that were not reviewed as model text |
| (c) Editing service (below) | the `.c4` files in the clone, written by `PUT /api/file` | yes: `POST /api/submit` runs `submit`, which commits the model directory to a `model/*` branch | no: one copy, the clone; the page reloads from disk |

The answer to "are edits written to the `.c4` files, or exported and merged?" is: in (c) they are
written to the `.c4` files in the fresh clone, and the branch is made by `submit`. Nothing is
exported and merged. (a) has no such path.

## The editing service

Not the playground and not code-server: a small separate service for the same job.

| Piece | Where |
| --- | --- |
| Backend (stdlib Python, HTTP API, Basic auth) | `tools/web_editor.py`, tests `tools/tests/test_web_editor.py` |
| Page (plain HTML/JS, no third-party code): text area left, `likec4 start` in an iframe right | `tools/web_editor.html` |
| Entrypoint switch `EDITOR_UI=web`, `RENDER_URL`, `HMR_PORT` | `docker/editor/entrypoint.py`, tests `tools/tests/test_entrypoint.py` |
| Image (node + `likec4@1.59.4` + python3 + git, no code-server) | `docker/editor/likec4-web/Containerfile` |
| Service `editor-likec4-web` | `docker/compose.editor.yml` |
| Run | `just editor-build`, `just poc-remote`, `just editor-up likec4-web` (needs `PASSWORD`, `MODEL_USER`, `MODEL_SLUG`) |
| Self-built playground (feedback 2) | `docker/editor/likec4-playground/Containerfile`, `nginx.conf`, service `likec4-playground`, `just playground-build`, `just playground-up` (port 8096) |

Ports, all 127.0.0.1 (**verified locally**, `podman port poc-editor-likec4-web`):
`8080/tcp -> 127.0.0.1:8094` (page and API), `5173/tcp -> 127.0.0.1:8095` (dev server),
`24679/tcp -> 127.0.0.1:24679` (Vite HMR websocket, fixed with `likec4 start --hmr-port`).

What the API does: `GET /api/files`, `GET`/`PUT /api/file?path=`, `POST /api/validate`
(`likec4 validate` and `likec4 format --check`), `POST /api/format`, `POST /api/submit`
(calls `submit.submit("likec4", <model path>, <clone>, message)`), `GET /api/status`. Paths must
be relative, stay in the model directory (symlinks are resolved first) and end in `.c4`. Writes
go to a temporary file and `os.replace`. Every request needs Basic auth with `PASSWORD`
(constant-time compare); every non-GET needs `Origin` equal to the page's own origin; the
process refuses to start without `PASSWORD`. Unit-tested (`uv run --locked pytest -q`); the
symlink test is skipped on this Windows host (no symlink right) and runs where symlinks work.

### Measurements (verified locally, throwaway password, `MODEL_USER=ada`, `MODEL_SLUG=web-e1`)

- Cold start: `just editor-up likec4-web` until both `http://127.0.0.1:8094/` (with the
  password) and `http://127.0.0.1:8095/` return 200: **23 s** (images already built).
- Image: 717 MB (`localhost/aac-editor-likec4-web:poc`), against 1.44 GB for the code-server
  image. `podman image inspect ... --format "{{.Config.Env}}"` shows only `PATH`,
  `NODE_VERSION`, `YARN_VERSION`, `RENDERER`, `MODEL_PATH`, `EDITOR_UI`: no password or token.
  `command -v code-server` in the container exits 127. The process runs as uid 1000
  (`coder`), Python 3.13.5.
- Auth: `curl http://127.0.0.1:8094/` returns 401; with the password 200.
- Save to re-render, server side: 5 runs of `PUT /api/file` (a description change) then waiting
  for `hmr update ...` in `podman logs --timestamps`. The log line's timestamp minus the start
  of the PUT: **0.16 to 0.28 s** (0.24, 0.28, 0.23, 0.16, 0.18; host and VM clocks differ by
  less than about 0.1 s). The PUT itself took 16 to 23 ms. The earlier PoC
  measured 0.2 to 0.3 s for the browser's HMR-and-render step with headless Chrome; the
  whole path in the page is in the next bullets.
- E1, E2 and E3 (same text as in [likec4-trial-poc.md](likec4-trial-poc.md#method)) were made
  with `PUT /api/file` + `POST /api/validate` + `POST /api/submit`. All three were sent in one
  session, so they are three commits on one branch `model/ada/2026-10-10-web-e1` (the earlier
  PoC used one branch per edit; the bare remote rejects a reused branch name, which is why one
  session is one branch). In the bare remote:

  ```
  $ git --git-dir=/remote/repo.git log --oneline main..model/ada/2026-10-10-web-e1
  b59c795 api description
  2250a97 worker calls notifications
  17a3435 add notification service
  $ git --git-dir=/remote/repo.git diff --stat main..model/ada/2026-10-10-web-e1
   trial/likec4/shop/model.c4 | 13 ++++++++++++-
   1 file changed, 12 insertions(+), 1 deletion(-)
  $ git ls-remote origin     # inside the clone
  ab4d14d14a064e08b2e5788b73ceed678cf6c298  refs/heads/main
  b59c795cbb54a4653fce2379482ba82f5a07ec4f  refs/heads/model/ada/2026-10-10-web-e1
  ```

  `main` in the bare remote stayed at the seeded `ab4d14d` (`git rev-parse main` before and
  after). The host repository's `main` is still `139e0ce`; no commit or push was made there.
  Each submit printed the `gh pr create` line; nothing ran it.
- Refusals: with the clone switched to `main`, `POST /api/submit` returned 422
  `refusing to submit from 'main': check out a model/* branch`. With a broken file (appended
  `this is not valid {{{`), `POST /api/validate` returned `ok: false` (`likec4 validate` exit 1),
  and `POST /api/submit` returned 422 `likec4 validate failed (exit 1)`; nothing was committed.
  The file was restored afterwards.
- In the page (AI stand-in, not a real non-technical user; `MODEL_SLUG=browser-r1`, screenshots
  in `build/trial-runs/web-editor/`, details in `build/trial-runs/browser-results.md`): 8095
  returned 200 13 s after `editor-up`; 8094 returned 401 without the password; Basic auth worked
  in the browser and the page showed `Branch: model/standin/2026-10-10-browser-r1`. E3 typed over
  "Accepts and tracks orders." at 20 ms per key (1.2 s): the page showed "saved" and **the
  iframe showed the new text 1.1 s after the last keystroke, with no reload**, including the 800
  ms autosave debounce. The iframe can frame 8095, the HMR websocket connected to
  `ws://127.0.0.1:24679/`, and the page contacted only 127.0.0.1:8094 and 8095. Validate showed
  "VALID"; Submit pushed `3bb9d07 Describe order validation in the API`
  (`trial/likec4/shop/model.c4 | 2 +-`). Submit asks for the message with a plain
  `window.prompt`, a small UX wart.

## Owner assumptions (local setup)

1. **Two services (read-only viewer vs editing service)**: locally these are two containers
   from different recipes. The editing service is `editor-likec4-web`: page on 8094, diagram on
   8095. The existing `editor-likec4` (code-server, diagram on 8093) stays. A read-only viewer
   that shows `main` by default is **not built** (deferred); the diagram on 8095 is the dev
   server of the editing clone and is not read-only (its "Edit" mode writes `.snap` files, see
   feedback 1), and it has no password of its own. That is acceptable on 127.0.0.1 only and
   would be a gap in any hosted setup.
2. **Editing only on a feature branch, never `main`**: the entrypoint checks out
   `model/<user>/<date>-<slug>` and aborts if the clone is on `main`; `submit` refuses `main`
   and any other branch name. Measured: submit on `main` is refused (above).
3. **How the container loads the model**: a fresh clone of the local bare remote
   `build/poc-remote.git`, mounted at `/remote/repo.git`, `REPO_URL=/remote/repo.git`, into
   `build/editor/likec4-web/model` (emptied by `just editor-up`). No new clone or auth logic.
4. **How the change reaches a branch and a PR**: `submit` commits the model directory and sends
   the branch to the local bare remote, and prints `gh pr create ...`. Nothing opens a PR.
5. **Is a wrapper around LikeC4 needed?** Yes, for this local flow. LikeC4's CLI provides
   `start` (live diagram, optional layout editing), `validate`, `format`, but no editor, no
   file write API and no branch or submit handling. The wrapper here provides: the text editor
   page, the file API with path guards, the password, validate/format buttons, branch handling
   at start, and `submit`. The language server in the browser (completion, hover) is not part of
   it: the page uses a plain `textarea`.

## Deferred to a later task

- Hosted git providers (GitHub, GitLab, others): clone and auth, push, PR or MR creation.
- How the model code reaches a hosted container.
- A read-only viewer where the branch can be selected (default `main`).

## What is not measured

- Any run by a real person: all browser results are one AI stand-in run each.
- Behaviour with several users or with the dev server's layout edit on a shared clone.

## Problems hit

| Problem | Cause | What fixed it |
| --- | --- | --- |
| `SyntaxError: multiple exception types must be parenthesized` when the container started | `ruff format` for Python 3.14 rewrote `except (A, B):` to the 3.14-only `except A, B:`; the image has Python 3.13 | one `except ValueError` (both are subclasses); the unit tests ran on 3.14 and could not see it |
| `usermod`/`useradd` for uid 1000 in the node image | the base image already has user `node` with uid 1000 | rename it to `coder` so paths match the other images |
| `git clone` of the LikeC4 source failed with an SSL CA error | `node:...-slim` has no `ca-certificates` | installed it in the throwaway clone container only |
| `likec4 validate` output had ANSI colour codes in the page | the CLI colours its log lines | stripped in `web_editor.py` |
| A body the server had not read made the client see a connection reset (flaky test, found by `just check`) | `POST /api/validate` answered without reading the request body | `web_editor.py` reads the whole body first for every non-GET request |
| Some shell removal commands were refused by the safety check | removal inside `sh -c` scripts | not worked around; the hand-made `.snap` test was dropped, the real drag was measured in the browser instead |

## Limits and recommendation

One machine (Podman on Windows), one assistant, one run per cell. The browser results are from an
AI stand-in, so none of them is a real user's experience. The recommendation for the owner, not
a decision: the editing service works end to end on the local setup with only the `.c4` files
written by the page itself; decide whether `.likec4/*.snap` layout files belong in the PR
(a drag today adds a 586-line file to it) before using the dev server's layout editing next to it. A richer editor (Monaco with the language
server, as the playground has) is a follow-up; the plain textarea gives no completion.
