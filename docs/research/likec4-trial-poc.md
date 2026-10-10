# LikeC4 trial: local PoC of the browser-editor path in both tools

Status: measurements from one machine and one assistant, 2026-10-10. Indicative, not a
benchmark. Part of the trial in
[ADR 0005](../decisions/0005-trial-likec4-for-the-editor-path.md); the claims it tests are in
[likec4-comparison.md](likec4-comparison.md). The owner decides after reading this; nothing
here changes the decision.

Labels: **verified locally** (with the command or file), **from docs** (as in the comparison),
**not measurable** (with the reason). Every result from the "AI stand-in" actor carries
the label *AI stand-in, not a real non-technical user*; see [Actor (a)](#actor-a-ai-stand-in-for-a-person).

## What was built

Two editor containers that differ only in the modelling tool (Flow B1 in
[workflow.md](../workflow.md)), a local bare repository standing in for GitHub, and a
`submit` command.

| Piece | Where |
| --- | --- |
| LikeC4 port of `examples/shop` | `trial/likec4/shop/model.c4` (see [its README](../../trial/likec4/README.md)) |
| Check of the port | `just trial-check` (`likec4 validate`, `likec4 format --check`, image `docker.io/likec4/likec4:1.59.4`) |
| `submit` | `tools/submit.py`, tests in `tools/tests/test_submit.py` |
| Local PR target | `build/poc-remote.git`, made by `just poc-remote` (`tools/poc_remote.py`, tests in `tools/tests/test_poc_remote.py`) |
| Entrypoint of both images | `docker/editor/entrypoint.py` |
| Structurizr editor image | `docker/editor/structurizr/Containerfile` |
| LikeC4 editor image | `docker/editor/likec4/Containerfile` |
| Containers and ports | `docker/compose.editor.yml` |
| Recipes | `just editor-build`, `just poc-remote`, `just editor-up TOOL=<structurizr or likec4>`, `just editor-down` |

How a session works: `editor-up` empties `build/editor/<tool>/model`, the entrypoint clones
`/remote/repo.git` (the bare repository, mounted) there, checks out
`model/<user>/<yyyy-mm-dd>-<slug>`, starts the renderer (`structurizr local` with
`STRUCTURIZR_EDITABLE=false` and `STRUCTURIZR_AUTOREFRESHINTERVAL=2000`, or `likec4 start`)
and then code-server. `submit` refuses `main` and any branch that is not
`model/<user>/<yyyy-mm-dd>-<slug>`, validates (Structurizr: `structurizr validate -w
examples/shop/workspace.dsl`; LikeC4: `likec4 validate` then `likec4 format --check`),
refuses an empty change, commits only the model directory, sends the branch to `origin` as
`HEAD:refs/heads/<branch>` and prints the `gh pr create` command. It never runs `gh` and
handles no token (PoC mode: no PR was opened).

Ports, all on 127.0.0.1 (**verified locally**, `podman port poc-editor-<tool>`):
Structurizr code-server 8090 and render 8091; LikeC4 code-server 8092 and dev server 8093.
The dev server was reachable from the host on the published port; the unreachable port in
the earlier probe ([comparison row 4](likec4-comparison.md)) did not recur with
`likec4 start --listen 0.0.0.0 --port 5173 --no-use-dot`, and I did not find out why the
earlier probe failed.

## Method

Owner decisions that shaped the runs (task.md, 2026-10-10):

1. The PR target is the local bare repository `build/poc-remote.git`. No GitHub remote exists;
   `submit` only prints the `gh pr create` line.
2. The person in the browser editor is replaced by an **AI stand-in** driving the browser.
3. Commits and pushes happen only inside the editor containers (and the seed container) and
   only to `build/poc-remote.git`. The host repository got no commit and no push.
4. The AI-assisted run is a **fresh Claude Code session** with no access to the research docs.
5. Ports 8090-8093 on 127.0.0.1; directory `trial/likec4/shop`.

Three edits per tool: **E1** add container `notifications` "Notification Service" ("Sends
order and shipping emails.", "Python") inside `shop`, with a deployment instance carrying
Kubernetes kind `Deployment` and name `shop-notifications`; **E2** add the relationship
`shop.worker -> shop.notifications` "Requests shipping email via" "HTTPS"; **E3** change the
description of `shop.api` to "Accepts, validates and tracks orders.". Each edit ends with a
`submit` inside the container that reaches its branch in `build/poc-remote.git`.

### Fresh Claude Code session: setup and bias controls

Started headless from the host, one session per tool, with the clone as working directory
(`build/editor/<tool>/model`), model `claude-sonnet-5-5` (from the transcript):

```
claude -p "<prompt>" --output-format stream-json --verbose \
  --settings build/trial-runs/settings-<tool>.json --setting-sources local \
  --disable-slash-commands --strict-mcp-config --max-budget-usd 6 \
  --allowedTools Read Edit Write Glob Grep WebFetch "Bash(podman exec poc-editor-<tool>:*)"
```

with `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` and `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`. Transcripts:
`build/trial-runs/transcript-<tool>.jsonl` (not committed; `build/` is gitignored).

Controls, and what they do not cover:

- The container was started with `SPARSE_EXCLUDE="docs README.md CLAUDE.md .claude tools docker
  .github justfile prek.toml pyproject.toml uv.lock .env.example"` plus the other tool's
  directory (`trial` for Structurizr, `examples` for LikeC4), so the clone held only the
  model file (plus `.gitignore`, `.gitattributes`, `.python-version`).
- The settings file denies `Read` of `docs/**`, `README.md`, `CLAUDE.md`, the other tool's
  directory and `.work/**` in the host repository and the worktree, and the Bash prefixes
  `git log`, `git show`, `git -C`, `cat` and `curl`. The clone sits inside the worktree on
  the host, so the denies matter; the session tried `cat docs/conventions.md` once (Structurizr
  run) and was refused (recorded in `permission_denials`).
- Skills, user and project settings, MCP servers, CLAUDE.md files and auto memory were off.
- Not controlled: the model knows both languages from training. Neither session fetched the
  official docs (no `WebFetch` calls in either transcript); both worked from the existing
  model file and prior knowledge. One run per tool.

Prompt (identical except the values in braces; the Structurizr run used
`Structurizr DSL`, `examples/shop/workspace.dsl`, `https://docs.structurizr.com/dsl/language`;
the LikeC4 run used `LikeC4 DSL`, `trial/likec4/shop/model.c4`, `https://likec4.dev (a
plain-text version of the docs is at https://likec4.dev/llms.txt)`; `{tool}` is `structurizr`
or `likec4`, so the LikeC4 prompt says "written in likec4"):

```
This directory is a git clone of a team's architecture model, written in {tool} ({language}). The model file is {file}. The official documentation for the language is at {url}. Use only that documentation and the files in this directory; do not read anything outside this directory.

Make three changes to the model, one after another, and submit each one before you start the next:

1. Add a container with identifier "notifications", name "Notification Service", description "Sends order and shipping emails.", technology "Python", inside the Shop system. Also add a deployment instance of it in the existing "local-kind" deployment environment, in the same Kubernetes namespace node as the other instances, with Kubernetes kind "Deployment" and Kubernetes name "shop-notifications". Record the Kubernetes information the same way the existing instances do.
2. Add a relationship from the Fulfilment Worker (shop.worker) to the new notifications container, described "Requests shipping email via", technology "HTTPS".
3. Change the description of the Order API container (shop.api) to "Accepts, validates and tracks orders."

Edit the files in this directory directly. The tools to check and submit the model are not installed on this machine; they are in a container that sees the same files. To validate and submit the model in one step run:

    podman exec poc-editor-{tool} sh -c 'cd /home/coder/model && submit -m "<short commit message>"'

`submit` validates the model, commits it and sends your branch to the team's remote. Do not use git yourself to commit or send anything. If validation fails, read the error, fix the model and run submit again. Stop after the third successful submit and report briefly what you changed.
```

### Actor (a): AI stand-in for a person

**AI stand-in, not a real non-technical user.** The implementer session had no browser
automation, so the orchestrator session ran this part at the owner's request (the owner
approved the exception). The Claude-in-Chrome extension connected but could not take
screenshots, so the browser was a headless Chrome (1440x900) driven through Playwright (CDP),
one action per step with a screenshot after each step. Input was keyboard and mouse only, in
code-server's editor, its find/replace widget and integrated terminal, and in the renderer
page. Raw notes and screenshots: `build/trial-runs/standin-results.md`, `standin-structurizr/`,
`standin-likec4/` (not committed). Screenshots 076-085 of the LikeC4 run were deleted because
they showed the throwaway code-server password. Branches in the bare remote:
`model/standin/2026-10-10-standin-structurizr` and `model/standin/2026-10-10-standin-likec4`;
`main` there stayed `13d2a57`.

Bias: the stand-in knows both DSLs, has read the research, and looked up the target line
numbers in the clone before typing. Times are a lower bound for a person and overstate ease
of use; the obstacles are the useful part.

Also checked: the code-server login pages answer 200 on 8090 and 8092, and the LikeC4
extension installs in the image (`Extension 'likec4.likec4-vscode' v1.59.4 was successfully
installed.`).

## Results

### Edits by a fresh Claude Code session (one run per tool)

Times are from the branch commit timestamps in the bare repository and the transcript
(`duration_ms`); the clock starts when `claude` starts.

| Measure | Structurizr | LikeC4 |
| --- | --- | --- |
| Session wall clock (start to end) | 56 s (13:41:54 to 13:42:50); `duration_ms` 47,091, API time 27,102 | 53 s (13:43:03 to 13:43:56); `duration_ms` 45,799, API time 23,613 |
| E1 clean `submit` after | 27 s | 18 s |
| E2 clean `submit` after | 42 s | 40 s |
| E3 clean `submit` after | 50 s | 48 s |
| `submit` runs (validator runs) | 4 (3 clean, 1 failed) | 4 (3 clean, 1 failed) |
| Errors before the first clean pass of that edit | E2: 1 | E2: 1 |
| First error text | `The destination element "payments"Charges" does not exist at line 25 of /home/coder/model/examples/shop/workspace.dsl: shop.api -> payments"Charges cards via" "HTTPS"` (the session's own edit had eaten a space) | `submit: likec4 format --check failed (exit 1): ... likec4.c4:format 1 of 1 file(s) need formatting: model.c4` |
| `format --check` failure | not applicable (no Structurizr formatter) | 1, fixed by running `likec4 format` in the container and submitting again |
| Tool calls (total) | 12: Read 1, Glob 1, Edit 5, Bash 5 (1 denied `cat`, 4 `submit`) | 10: Read 1, Edit 4, Bash 5 (4 `submit`, 1 `likec4 format` plus `git diff`) |
| Turns, cost | 13 turns, USD 0.106 | 11 turns, USD 0.062 |
| Tokens | input 20, cache created 17,836, cache read 139,388, output 2,077 | input 14, cache created 7,906, cache read 105,888, output 1,989 |
| Preview updated without a manual refresh, delay | not measurable: no browser in these sessions (the stand-in browser results are below; server-side timings are in the renderer table) | same |
| Diff, `git diff --stat main..<branch>` in the bare repo | 1 file, +9 -1 (`examples/shop/workspace.dsl`) | 1 file, +12 -1 (`trial/likec4/shop/model.c4`) |
| Per-commit diff (E1, E2, E3) | +7; +1; +1 -1 | +10; +1; +1 -1 |
| Kubernetes data written | `"kubernetes.kind" "Deployment"`, `"kubernetes.name" "shop-notifications"` (same style as existing) | `kubernetes_kind 'Deployment'`, `kubernetes_name 'shop-notifications'` |
| Docs fetched | none | none |

Both sessions produced the requested model; each edit's branch result is valid (every
commit passed the container's validator, which `submit` runs before committing).

### Edits by the AI stand-in for a person (AI stand-in, not a real non-technical user)

All results in this subsection: **AI stand-in, not a real non-technical user** (method and
bias in [Actor (a)](#actor-a-ai-stand-in-for-a-person)). Each edit had one validator run and
no error before the first clean pass.

| Tool | Edit | Wall clock to clean `submit` | Validator runs / errors | `format --check` | Diff of the edit's commit | Preview |
| --- | --- | --- | --- | --- | --- | --- |
| Structurizr | E1 | 3 min 34 s | 1 / 0 | n/a | 1 file, +7 | new container shown on page load; delay not applicable (loaded after the edit) |
| Structurizr | E2 | 1 min 28 s | 1 / 0 | n/a | 1 file, +1 | updated without reload; delay not timed per edit (one separate probe: within 10 s, see live preview below) |
| Structurizr | E3 | 41 s | 1 / 0 | n/a | 1 file, +1 -1 | updated without reload; delay not timed per edit (same probe) |
| LikeC4 | E1 | 2 min 23 s (includes a renderer check) | 1 / 0 (the editor showed 4 transient problems while typing, 0 after save) | pass | 1 file, +10 | new container shown on page load; delay not applicable (loaded after the edit) |
| LikeC4 | E2 | 36 s | 1 / 0 | pass | 1 file, +1 | needed a page reload (HMR port 24678 was not published then).  Re-measured in round 2 with the port published: updates without reload, 0.2 to 0.3 s (in-container file write, page polled; see live preview below) |
| LikeC4 | E3 | 39 s | 1 / 0 | pass | 1 file, +1 -1 | needed a page reload (same cause).  Same re-measure: updates without reload in 0.2 to 0.3 s |

Per-edit diffs are the per-commit `git show --stat` of each branch in the bare remote
(saved in `build/trial-runs/standin-per-edit-stats.txt` because `editor-up` wipes the clones).
Whole-branch diff, `git diff --stat main..<branch>`: Structurizr
`examples/shop/workspace.dsl | 10 +++++++++-` (+9 -1, 3 commits); LikeC4
`trial/likec4/shop/model.c4 | 13 ++++++++++++-` (+12 -1, 3 commits). LikeC4's renderer
returned HTTP 200 on 8093 13 s after `just editor-up TOOL=likec4`; Structurizr's renderer start
was not measured in this run (see the cold-start row below).

UI obstacles (**AI stand-in, not a real non-technical user**):

- Both editors, C1: code-server opens in Restricted Mode with a banner, and the first terminal
  opens a modal "Do you trust the authors of the files in this folder?" (`Trust Folder & Continue`).
  A non-technical person must accept a security prompt before they can run `submit`.
- Both, C2: a Chat panel ("Build with Agent") is open on the right by default.
- Both, C3: Explorer and status bar still show the file as modified (`M`) after `submit` committed
  it (stale git decoration), unclear whether the change was sent.
- Both, C4: auto-indent leaves trailing spaces on a new blank line if you save with the cursor on
  it (hit in Structurizr E2, fixed by hand).
- Structurizr S1: the Enter confirming Ctrl+G (go to line) merged with the next keystrokes, so
  the new container line was appended to line 13; E2 then landed one line too low and
  unindented. Nothing flagged this before `submit` (the Structurizr extension is highlighting only).
- LikeC4 L0: code-server's login cookie is per host, not per port, so after logging in on 8090 the
  editor on 8092 was already logged in and the typed password went into an "Open Folder" dialog
  (cancelled). Two editors on one host share the session.
- LikeC4 L1: transient errors (Problems: 4) while a block is incomplete, cleared on save; helpful
  for real mistakes, a little alarming mid-edit.

Representative screenshots (not committed; in `build/trial-runs/`), **AI stand-in**:

- `standin-structurizr/040-wait.png`: code-server with `workspace.dsl` open (the new
  `containerInstance shop.notifications` block highlighted in the gutter, file still marked `M`),
  the Structurizr language shown in the status bar, and the terminal after the first `submit`:
  `structurizr validate -w examples/shop/workspace.dsl`, then the pushed branch and the printed
  `gh pr create` line.
- `standin-likec4/164-wait.png`: code-server with `model.c4`, the terminal showing two successful
  `submit` runs (`likec4 validate`, `likec4 format --check`), and the "Diagram Preview" tab on the
  right completely blank.
- `standin-structurizr/071-renderer-deployment.png` and `standin-likec4/150-renderer-deployment.png`
  (not re-opened here; described in `standin-results.md`): the deployment views after E1-E3.

### Live preview without a manual refresh (AI stand-in, not a real non-technical user)

- **Structurizr `local` (8091): yes.** With the Deployment view open, a change to the DSL appeared
  within 10 s without reloading (edit the file, wait, revert).
- **LikeC4 `likec4 start` (8093): no with the port unpublished (round 1), yes after the fix (round 2, below).** The server sees the change (log
  `hmr update likec4:plugin/default/model.js`, see the table below) but the page stays stale until
  reload. Cause, from the browser console: the Vite HMR client connects to `ws://127.0.0.1:24678/`
  and gets `ERR_CONNECTION_REFUSED`, because `docker/compose.editor.yml` published only 5173 as
  8093. **Fixed in round 2**: `docker/compose.editor.yml` now also publishes
  `127.0.0.1:24678:24678` (`podman port poc-editor-likec4` lists it; `curl` to it returns 426,
  the WebSocket upgrade answer, so Vite's HMR server is reachable). **Re-measured in round 2 (AI stand-in session, headless Chrome, not a real user):**
  with 24678 published, the page's Vite client connected to `ws://127.0.0.1:24678/` and the page
  updated without a reload in 0.3, 0.2, 0.2 and 0.2 s (four description changes of `shop.db`
  and back). Method: the file was changed inside the container with `sed -i`, which is the
  same write a code-server save makes, and the page was polled every 200 ms; a first attempt
  typing through code-server's find/replace did not save (driver problem) and is not counted.
  So the "no" above was caused by our unpublished port, not by LikeC4: **yes, delay well under
  1 s**. Structurizr by comparison: within 10 s, one probe.
- **LikeC4 VS Code extension preview inside code-server: no.** "LikeC4: Open Preview" opens a
  "Diagram Preview" tab that stays blank (checked after 18 s). The webview loads its script from a
  `vscode-resource.vscode-cdn.net/.../likec4-vscode-1.59.4-universal/dist/preview/index.js` URL and
  never renders; cause not confirmed. The extension's language server did work: live diagnostics
  in Problems, an `open preview` code lens, breadcrumbs.

### Renderer behaviour (no browser; measured on the server side)

| Measure | Structurizr (`structurizr local`) | LikeC4 (`likec4 start`) |
| --- | --- | --- |
| Data updates after a save from the host (edit on the bind-mounted clone) | `/api/workspace/1` showed the new text 0.35 to 1.18 s after the save (5 runs: 0.63, 0.35, 0.64, 1.18 and 0.34 s); `/workspace/lastModified` changed 0.27 to 0.93 s after | log line `hmr update likec4:plugin/default/model.js` seen 0.3 s after the save in 4 of 4 runs (polling every 0.25 s, so 0.3 s is the resolution) |
| What the browser still has to do | poll `lastModified` every 2 s (`STRUCTURIZR_AUTOREFRESHINTERVAL=2000`) and reload: up to about 2 s more, **from docs**, not observed | receive the HMR message and re-render, **from docs**, not observed |
| File watching on the Windows bind mount | not needed (the server reads on request) | worked with `CHOKIDAR_USEPOLLING=true` set by the entrypoint; not tested without it |
| Caveat | none seen | fetching `/@id/likec4:model/default` right after a change sometimes returned a connection reset or took 19 s; the log-based figure is the reliable one |

### Sizes, build and start times, licences

| Measure | Structurizr editor | LikeC4 editor |
| --- | --- | --- |
| Image size (`podman images`) | 1.55 GB | 1.44 GB |
| Base `codercom/code-server:4.141.0-trixie` | 1.08 GB | 1.08 GB |
| First build | `just editor-build` built both images in 2 min 12 s with the base images already pulled (pull time not included); a rebuild after changing one layer: 1 min 36 s | (same run) |
| Cold start of `just editor-up` (container removed, images local, fresh clone) | `editor-up` returned in 4.3 s; code-server login page at 8.4 s; renderer at 28.9 s (JVM start) | returned in 4.1 s; login page at 8.7 s; renderer at 9.3 s |
| Pinned versions | code-server 4.141.0, Structurizr 2026.09.19 (war copied from the pinned image), Debian OpenJDK 21 JRE, extension `ciarant.vscode-structurizr` 0.0.9 | code-server 4.141.0, Node 22.22.3, `likec4` 1.59.4 (npm), extension `likec4.likec4-vscode` 1.59.4 |
| Licences | code-server MIT (`package.json` in the image); Structurizr vNext Apache-2.0 (from the research doc, not rechecked); OpenJDK GPL-2.0 with Classpath Exception (`/usr/share/doc/openjdk-21-jre-headless/copyright`); Python PSF and git GPL-2.0 (Debian); extension MIT (Open VSX metadata) | code-server MIT; likec4 MIT (npm registry); Node.js MIT; extension MIT (Open VSX metadata); Python PSF and git GPL-2.0 (Debian) |
| Environment of the image | no `PASSWORD` or token (`podman image inspect`); only `RENDERER` and `MODEL_PATH` | same |

Why a custom JRE: `docker.io/structurizr/structurizr` is Alpine (musl) with a shell-less
Temurin JRE, so the war is copied out and run by the Debian JRE of the code-server base.
No legacy Structurizr image is involved.

### The port

Command: `podman run --rm -v ./trial/likec4/shop:/data:ro -v <out>:/out docker.io/likec4/likec4:1.59.4 export json -o /out/model.json`, then reading `deployments.elements` from `model.json`. `just trial-check` passes: `✓ Valid (1 files)` and `All 1 file(s) are formatted`. The deployment
metadata survives under `kubernetes_*` keys (**verified locally**, `likec4 export json`,
`deployments.elements`):

```
localKind.cluster.shopNamespace          {'kubernetes_namespace': 'shop'}
localKind.cluster.shopNamespace.web      {'kubernetes_kind': 'Deployment', 'kubernetes_name': 'shop-web'}
localKind.cluster.shopNamespace.api      {'kubernetes_kind': 'Deployment', 'kubernetes_name': 'shop-api'}
localKind.cluster.shopNamespace.worker   {'kubernetes_kind': 'Deployment', 'kubernetes_name': 'shop-worker'}
localKind.cluster.shopNamespace.db       {'kubernetes_kind': 'StatefulSet', 'kubernetes_name': 'shop-db'}
```

Port differences worth knowing: element kinds (`person`, `softwareSystem`, `container`,
`deploymentNode`, `environment`) must be declared in a `specification` block; the deployment
environment is a node kind (`localKind = environment 'local-kind'`); the shape styles are
set per element, and the colours of the DSL's `styles` block were not ported. The DSL's `shape person` for the Person element was not ported either (shapes in the port are the defaults).

## Result per criterion

1. **User-friendly for non-technical users**: no tool is ahead on the evidence. No real person took part; the **AI stand-in, not a real non-technical user**
   (who knows both DSLs and overstates ease) edited both with the same keyboard-and-mouse
   steps. Edit times were similar (E1 3 min 34 s against 2 min 23 s, E2 1 min 28 s against
   36 s, E3 41 s against 39 s; LikeC4 faster, but the stand-in had learned the file by then).
   Both share the code-server obstacles C1-C4, which a non-technical person would meet in
   either. The preview gap seen in round 1 (LikeC4's page needed a reload) came from our own
   config, not the tool: with the HMR port published, LikeC4's page updates in 0.2 to 0.3 s
   (AI stand-in, in-container write method) against Structurizr's "within 10 s" (one probe),
   so LikeC4 is at least equal there. The LikeC4 extension's preview in code-server still
   stayed blank (cause not confirmed). LikeC4's language server did give live
   diagnostics, which Structurizr's highlight-only extension does not (obstacle S1 went
   unflagged until `submit`). LikeC4 has the faster page preview and live diagnostics; its in-editor preview was blank. Real-user runs are still missing and would decide.
2. **Free**: tie, **verified locally** for the components in both images: MIT, Apache-2.0 and
   GPL-2.0 with Classpath Exception; no paid component, no SaaS. LikeC4's editor image is 0.11 GB
   smaller here (1.44 against 1.55 GB) because both sit on the 1.08 GB code-server base.
3. **AI-friendly**: both tools worked for a fresh session without their docs: three correct
   edits, one failed validation each, finished in about 50 s. LikeC4 was cheaper (USD 0.062
   against 0.106) and used fewer tool calls (10 against 12), and `format --check` made the
   canonical form enforceable, which Structurizr cannot do. One run per tool with
   a model that already knows both languages: a difference of this size is not evidence of
   which tool is better.

## Notes on the setup

- The editor setup is Podman only (`--userns=keep-id` and `userns_mode: keep-id` have no Docker
  equivalent); `poc-remote` and `editor-up` fail with `CONTAINER_ENGINE=docker`.
- Pinned: base images, code-server, Node, `likec4`, Structurizr and the extensions. Not pinned:
  the Debian packages `python3` and `openjdk-21-jre-headless` (taken from the trixie archive
  at build time) and the transitive npm dependencies of `likec4` 1.59.4.
- Round 2 checks (both tools, `just editor-up`): branch `model/ada/2026-10-10-ac9-<tool>`;
  8090/8091 return 302, 8092 302, 8093 200; `podman port` shows 127.0.0.1 bindings only; a
  file staged outside the model directory (`README.md`) stayed staged and was not committed;
  `submit` on `main` exited 1; both `model/*` branches exist in `build/poc-remote.git`;
  its `main` was unchanged. The renderer process of the Structurizr image has no `PASSWORD`
  in its environment.

## Problems hit

| Problem | Command or cause | What fixed it |
| --- | --- | --- |
| `git init` in a bind-mounted directory failed: `chmod ... config.lock failed: Operation not permitted` | Podman on a Windows host; the container user did not own the mount | `--userns=keep-id:uid=1000,gid=1000` on `podman run` and `userns_mode: "keep-id:uid=1000,gid=1000"` in `docker/compose.editor.yml` |
| Every file shows as executable in a clone on the bind mount | Windows host mounts | `core.fileMode=false` in the seed and in the clone |
| `shutil` missing in the image | `python3-minimal` has no full standard library | install `python3` |
| `structurizr local` failed with `Could not create data directory at /usr/local/structurizr` | it uses its argument, not the working directory, as the data directory | the entrypoint passes the model directory as an argument |
| `likec4 start`: `EACCES ... node_modules/.vite/deps_temp_...` | vite writes its cache inside the global package, owned by root | create `.vite` owned by `coder` in the Containerfile |
| `podman compose build` could not find the Containerfile; required variables broke `build` and `down` | podman-compose 1.x behaviour | `just editor-build` calls `podman build` directly; variables use `${NAME:-}` and the entrypoint refuses to start without them |
| `just editor-up TOOL=likec4` failed with `justfile does not contain recipe 'TOOL=likec4'` (round 1 of this PoC) | `NAME=value` is only a variable override before the recipe name | `editor-up` takes a parameter and strips a leading `TOOL=`, so `just editor-up TOOL=likec4`, `just editor-up likec4` and `just TOOL=likec4 editor-up` all work |
| `editor-up` could not empty the previous clone | git object files are read-only on Windows | the recipe chmods on error while removing |
| A second session with the same branch name was rejected as non-fast-forward | the branch already exists in the bare repository | use a new `MODEL_SLUG` per session (the rejection is the intended protection) |
| Non-cone sparse patterns with a trailing slash hid directories but left files | patterns like `!/docs/workflow.md/` match directories only | patterns without a trailing slash |
| LikeC4 page does not update after a save (stand-in browser run) | the Vite HMR WebSocket on 24678 is not published by `docker/compose.editor.yml` (`ERR_CONNECTION_REFUSED` in the console) | fixed in round 2: `docker/compose.editor.yml` now publishes `127.0.0.1:24678:24678`; the page updates without a reload in 0.2 to 0.3 s |
| LikeC4 extension "Diagram Preview" is blank inside code-server | cause not confirmed (webview script from `vscode-resource.vscode-cdn.net`) | open |
| A shell command containing the word "push" in a heredoc was blocked by the task hook | task-flow guard | wrote the text with the file tools instead; nothing was worked around |

## Smoke checks (verified locally)

- No change: `submit` prints `nothing to submit: no changes under <dir>` and exits 1 (both tools).
- After a trivial edit: the branch reaches `build/poc-remote.git` (both tools).
- On `main`: `submit: refusing to submit from 'main'` and exit 1 (both tools); `main` in the
  bare repository stayed at the seeded commit throughout (`13d2a57` after the last seed).
- Host repository: `main` still `ab29f43`, 3 commits, no remote configured.

## Limits

One machine (Podman 5.8.3 on Windows), one assistant, one run per cell. The fresh sessions
were not isolated from the model's training. The stand-in runs were done by an AI that knows
both tools; real-user runs are missing. Nothing here touched GitHub, a cluster or a real token.
