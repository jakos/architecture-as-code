# Model editor image: the LikeC4 playground plus our patch set

Status: spike, patch set and local measurements, 2026-10-11 and 2026-10-12. Indicative, from one
machine and one assistant. Decisions: [ADR 0007](../decisions/0007-model-editor-on-likec4-playground.md)
(the editor) and [ADR 0008](../decisions/0008-layout-snap-policy.md) (layout files).

Labels: **verified locally** (with the command or script), **from source at v1.59.4** (LikeC4 repo,
tag `v1.59.4`, commit `33dbc2d34c399a99daf96e92fc28fe5d280a7fd5`, cloned into `build/likec4-src/`
and into containers), **AI stand-in, not a real non-technical user** (a headless Chromium driven by
Playwright inside a container, run by the implementing assistant; no real person has used the
editor yet). The orchestrator's own browser run, with screenshots, is separate and is recorded
with the review, not here.

## Spike

Read at tag `v1.59.4`, `apps/playground`, about 5,900 lines of TypeScript and React (4,600 without
the example models).

| Question | Answer (from source at v1.59.4) |
| --- | --- |
| How does a workspace hold several files, and how do they reach Monaco and the language server? | `PlaygroundContext.files` in `src/state/playground-machine.ts` is a map from file name to text. `LanguageClientSync.tsx` creates one Monaco model and one in-memory file (`RegisteredMemoryFile`, URI `file:///<name>`) per entry (`createMemoryFileSystem` in `src/monaco/utils.ts`), then sends a single `BuildDocuments` request with all the URIs to the language server in the Web Worker. Nothing limits the count, so all 29 shop files load and cross-file references resolve (confirmed in a browser run below: 29 files, 22 views, no diagnostics). |
| Where does the file list or tab UI live? | `src/components/workspace/WorkspaceFileTabs.tsx`, rendered by `src/routes/w.$workspaceId/route.tsx`. A row of tabs, unusable for 29 files, so the patch replaces it with a tree. |
| Which components render Share, Login, the Playgrounds menu and the examples? | `src/components/appshell/Header.tsx` renders `ShareButton.tsx` (with `SharePlaygroundForm.tsx`, `shareFormState.ts`), `PlaygroundsMenu.tsx` (with `hooks/useWorkspaces.tsx`), `UserButton.tsx` ("Login with GitHub", link to `/auth/github`; `hooks/useUserSession.ts` calls `/auth/me`) and `PlaygroundTitle.tsx`. The examples are `src/examples/*`, read by `state/persistence.ts`, `hooks/useWorkspaces.tsx`, `hooks/usePlayground.ts` and the route loader. The Worker calls are `src/api.ts` (a hono client of `#worker/client`), used by the share actor in the state machine, the share routes `src/routes/share.$shareId/*`, `redirect-after-auth.tsx` and `useUserSession`. Fonts come from `cdn.jsdelivr.net` (`font-fira-code.css`, `font-ibm-plex-sans.css`, linked in `index.html`). |
| Where can a server-backed workspace be plugged in with the fewest edits? | Two places: the loader of `src/routes/w.$workspaceId/route.tsx` (it returns the `LocalWorkspace` that becomes the state machine's input), and the `'persist to storage'` action in `playground-machine.ts`, which is the one write path to storage (called by the debounced `workspace.persist` event, 1000 ms after the last keystroke, and on file switches). Replacing those two and the header and file list is enough; no change in the language-server wiring. |
| How can Monaco markers be set from outside the language server? | `monaco.editor.setModelMarkers(model, owner, markers)` on the same `@codingame/monaco-vscode-editor-api` object that `LanguageClientSync.tsx` uses. The language server's own diagnostics use another owner, so markers with the owner `aac-validate` coexist with them. |
| Does the playground render `.likec4/*.snap` manual layouts from workspace files? | No. The language server in the worker runs with `NoLikeC4ManualLayouts` (`packages/language-server/src/browser/index.ts`, `module.ts`), the client logs "Operation save-view-snapshot is ignored in Playground", and only `.c4` text is loaded. Curated layouts are therefore not shown (ADR 0008). |
| Is there a typecheck script? | Yes: `pnpm run typecheck` = `tsc --build --verbose` in `apps/playground`. It needs the libraries built first (the Containerfile runs it after the turbo build). |

### `likec4 validate` output (verified locally)

`docker.io/likec4/likec4:1.59.4`, run on a copy of `examples/shop` with one misspelled keyword
in `teams/orders/model.c4` and an unresolved reference in `shared/people.c4`
(`validate` and `format --check`, exit 1 for both; the output of both is kept as fixtures in
`tools/tests/fixtures/likec4_validate_broken.txt` and `likec4_format_check_broken.txt`, trimmed to
two files):

- It is a coloured log. Without colours, one line is `HH:MM:SS.mmm LEVEL category text`.
- A broken file is an `ERROR` line `Invalid <absolute path>` followed by indented
  `Line <n>: <message>` lines. **There is no column.** The path is as the CLI sees the model
  directory (`/data/...` in a container), so the server strips the model directory to get a
  model-relative path.
- A parser error is followed by more indented lines (the token list). The same parser error is
  often printed several times for one line.
- Errors in other files that follow from a broken one (an unresolved reference) are reported
  too, 40 errors in 9 files for this one typo.
- `format --check` prints `needs formatting <relative path>` (an `INFO` line) and a final `ERROR`
  line that lists the files; it repeats the validation errors.
- `validate` ends with `ERROR ... ✗ Invalid (29 files, 40 errors)`.

`tools/web_editor.py` turns this into `problems: [{path, line, column, severity, message}]`
(column is null) and keeps every line it does not recognise as a problem without a path.

### Patch size estimate and gate

Estimate before writing the patches, from the files above: 9 upstream files edited or deleted
plus the share routes (5 files, about 350 lines) to delete, about 150 lines changed elsewhere in
existing files, and all new UI in new files. That is about 500 lines in existing files and 14
files, against the gate of 800 lines or 25 files. Multi-file workspaces can be fed from the
route loader and the persist action without rewriting the state layer. **The gate passed**, so
the work continued. The measured size is below.

## Result

### Patch set size (verified locally: `just playground-patches-stat`)

| Patch | Existing upstream files (of which deleted) | Lines added | Lines removed | New files | New lines |
| --- | --- | --- | --- | --- | --- |
| `0001-remove-cloud-features.patch` | 9 (6) | 4 | 371 | 0 | 0 |
| `0002-server-workspace.patch` | 1 (0) | 8 | 14 | 2 | 182 |
| `0003-editor-ui.patch` | 2 (0) | 17 | 27 | 5 | 759 |
| **Total** | **12 (6)** | **29** | **412** | **7** | **941** |

Lines changed in existing upstream files: 29 added + 412 removed = **441**, in **12** files (the
gate was 800 lines or 25 files). 371 of the removed lines are the share routes and the GitHub
redirect route that the generated router would otherwise import. Nothing else upstream is deleted:
the Share, Login and Playgrounds components and the examples stay in the tree but nothing imports
them, so they are not in the bundle.

### Image (verified locally)

- `just model-editor-build`, cold (`podman build --no-cache`): 11 min 15 s (675 s; the same command as the recipe plus `--no-cache`, on a machine where the base image and the apt and npm downloads were warm). The log shows
  `LikeC4 v1.59.4 is commit 33dbc2d34c399a99daf96e92fc28fe5d280a7fd5`, the three lines
  `applied 0001-...`, `applied 0002-...`, `applied 0003-...`, and a clean `pnpm run typecheck`.
  The earlier `just playground-build` took 6 min 47 s on the same machine for the unpatched app.
- Size: 737 MB (`podman image ls`), of which the static app is 19 MB. The playground-only
  nginx image is 83 MB; the rest is Node, the `likec4` CLI, Python and git.
- `podman image inspect ... --format "{{.Config.Env}}"`:
  `[PATH=... NODE_VERSION=22.22.3 YARN_VERSION=1.22.22 RENDERER=likec4 MODEL_PATH=examples/shop EDITOR_UI=playground]`,
  no `PASSWORD` or token.
- `grep -rlE 'cdn.jsdelivr.net|Login with GitHub' /usr/local/share/model-editor` in the image finds
  nothing. `index.html` references only `/assets/...`.

### Running it (verified locally)

`just poc-remote`, then `PASSWORD=<throwaway> MODEL_USER=ada MODEL_SLUG=editor-image-trial just
editor-up model-editor`:

| Measure | Result |
| --- | --- |
| Start of `just editor-up` to the first `200` (compose up, fresh clone on the bind mount, server) | 44.5 s |
| `podman port poc-model-editor` | `8080/tcp -> 127.0.0.1:8097` only |
| `GET /` without the password | 401 |
| `GET /` with `-u ada:$PASSWORD` | 200 |
| `GET /api/workspace` | 29 files, branch `model/ada/2026-10-11-editor-image-trial` (`git ls-files 'examples/shop/*.c4'` also gives 29) |
| `PUT /api/file?path=teams/orders/model.c4` (description edit), then `.likec4/x.likec4.snap` created in the clone, then `POST /api/submit` | 200; `skipped: [".likec4/x.likec4.snap"]`; the output has `skipped (not committed): examples/shop/.likec4/x.likec4.snap` |
| `git --git-dir=build/poc-remote.git diff --stat main..model/ada/2026-10-11-editor-image-trial` | one file, `examples/shop/teams/orders/model.c4 | 2 +-`, one commit `Clarify orders description via API` |
| `rev-parse main` in the bare remote before and after | identical (`d54a40c`) |

#### Host path: truncated assets and the HTTP/1.1 fix (verified locally, round 2)

Round 1 review found that from the Windows host (Podman port forward to 127.0.0.1:8097) large
static responses were cut or reset: of 36 parallel `curl -u` GETs of the 3,151,923-byte main
JS, 2 came back short (3,140,312 and 3,144,600 bytes), and the page often loaded blank or
unstyled. The same 60 GETs inside the container were all complete. The handler answered
HTTP/1.0 and closed the connection after every response. Hypothesis: close-after-response
is what the forward cannot handle (`likec4 start`, Vite with keep-alive, never failed).

Change: `protocol_version = "HTTP/1.1"` and `timeout = 60` on the handler (every response
sends Content-Length; request bodies are drained by `_read_raw`). Test:
`test_keep_alive_serves_two_requests_on_one_connection`.

Measured after rebuilding the image and `just editor-up model-editor` (same host, same forward):

| Measure | Before | After |
| --- | --- | --- |
| Parallel GETs of `/assets/index-Bg7dP9j5.js`, 12 at a time | 34 of 36 complete | 108 of 108 complete (3 + 6 rounds of 12), all 3,151,923 bytes |

This supports the keep-alive hypothesis but does not prove it (the failure was
intermittent). Page loads in a browser from the host were not run by the implementer (no
Playwright in the subagent environment); they are queued as NEEDS-BROWSER in status.md.

AC12 re-run on the same container, from the host (`PUT /api/file` with a one-line
description edit of `teams/orders/model.c4`, `.likec4/x.likec4.snap` created with
`podman exec`, then `POST /api/submit`). The branch is left in `build/poc-remote.git`:

- `rev-parse main` before and after: `9fe289dd5b8194d4f077570556c62aabca211b0a` both times.
- Branch `model/ada/2026-10-11-check-r2`, one commit `Clarify orders description (round 2 check)`.
- `git --git-dir=build/poc-remote.git diff --stat main..model/ada/2026-10-11-check-r2`:
  `examples/shop/teams/orders/model.c4 | 2 +-`, 1 file changed, 1 insertion(+), 1 deletion(-).
- `skipped`: `[".likec4/x.likec4.snap"]`.

### Browser checks (AI stand-in, not a real non-technical user)

Headless Chromium 154.0.8037.92 (Debian 13 package) driven by Playwright in a container next to the real image
(`localhost/aac-model-editor:v1.59.4`), HTTP Basic credentials given to the browser context. These
are the implementer's own runs to find bugs; the NEEDS-BROWSER items in the task log are for the
orchestrator.

- Load: the editor shows Monaco with `views/index.c4`, the file tree with all 29 files in the
  folders `shared/`, `teams/<six domains>/`, `views/`, `views/dynamic/`, the live diagram
  ("Landscape", 22 views in the model), the header with the branch, the save state and the
  buttons Validate, Format and Submit. No Share, Login, Playgrounds or examples. The language
  server reports no diagnostics for the unmodified model (`diagnosticErrors` is empty).
- Only `http://<host>:8080` URLs are requested (every request in the page and its workers came
  from one origin; the only 404 is the browser's `/favicon.ico`, there is no icon link any more).
  localStorage holds `notation-webview-collapsed`; sessionStorage holds the open file name and
  the panel sizes. No model text.
- Autosave: after typing, the indicator is `unsaved` at once and `saved` about 0.8 to 0.9 s
  after the last keystroke (817 ms and 893 ms in two runs); the file in the clone changes.
- Ctrl+S saves at once. After a reload the text comes from the server.
- Validate with an unresolved reference: the Problems list shows the file, line and message
  (`teams/orders/model.c4:51 Could not resolve reference ...`), the tree shows a count next to the
  file, clicking a row opens the file at the line and the editor shows 5 error squiggles.
- Format: with a mis-indented line, Format saves, runs `likec4 format`, reloads the page and the
  server file is formatted.
- Submit: the dialog lists the changed files, asks for a message, shows the branch, the files that
  were skipped (an untracked `views/scratch.snap` and `.likec4/x.likec4.snap`), the printed
  `gh pr create` command with a Copy button, and the output. On the bare remote the branch has one
  commit with only `teams/orders/model.c4`, and `main` is unchanged.
- Console noise seen in every run, probably upstream's (not compared with an unpatched build):
  `AbortError: Transition was skipped` (the router's view transitions) and
  `Unhandled method likec4/build` logged by the language client while the model still builds.

### Upgrade trial (verified locally)

The pinned tag `v1.59.4` is the newest release tag of `likec4/likec4` (`git ls-remote --tags
https://github.com/likec4/likec4.git 'v1.*' | sort -V` ends at `v1.59.4`, 2026-10-12), so there is
no newer release to try. To see what an upgrade costs, the same check was run against the control
(the pin itself), two older tags (one patch and one minor release back) and the development branch.
Command, run in a container for each ref, with the three patches from
`docker/editor/model-editor/patches/`:

```
git clone --depth 1 --branch <ref> https://github.com/likec4/likec4.git /trial
cd /trial && for p in /patches/*.patch; do git apply --check "$p"; done      # each alone
cd /trial && for p in /patches/*.patch; do git apply --check "$p" && git apply "$p"; done   # in order
```

| Ref | 0001 | 0002 | 0003 | In order |
| --- | --- | --- | --- | --- |
| `v1.59.4` (the pin, commit `33dbc2d`) | applies | applies | applies | all three apply |
| `v1.59.0` (`97946d3`) | **rejected** | applies | applies | stops at 0001 |
| `v1.58.0` (`510a368`) | **rejected** | applies | applies | stops at 0001 |
| `main` (`f551975`, package version still 1.59.4) | **rejected** | applies | applies | stops at 0001 |

Rejected hunks, all in 0001:

- `v1.59.0` and `v1.58.0`: the deletions of `src/routes/share.$shareId/enter-pincode.tsx` and
  `src/routes/share.$shareId/view/$viewId.tsx` fail because those files differ from 1.59.4
  (a delete patch carries the old content). Fix: delete the two files again with `git rm` in a clone
  of the new tag and regenerate with `playground_patches.py export`; about 5 minutes.
- `main`: the hunk in `src/monaco/config.ts` at line 90 (the font family line) fails because the
  line changed upstream. Fix: re-edit that line by hand and regenerate; about 5 minutes.

0002 and 0003 apply on every ref because the files they touch did not change there (only
`git apply --check`: they were not built or typechecked against those refs, so an API change in
the playground state machine or in Mantine could still break them at compile time). The raw output
was kept in `build/upgrade-trial.txt` (not committed).

## Open questions and limits

- The AI stand-in checks above prove the flow works, not that it is easy to use for someone who
  has never seen the model. A real user test is still open.
- Basic auth under real browsers: Playwright's credentials option behaves like a login the browser
  already holds. A browser that does not send credentials to the module scripts or the language
  server worker would show 401 for them; a session cookie is the fallback (ADR 0007). Item (c) of
  the NEEDS-BROWSER list in the task log checks it with a real page load.
- Curated `.snap` layouts are not shown in the editor (ADR 0008).
- The editor opens and edits existing files only: no new, renamed or deleted files from the tree.
- Not covered: a model much larger than the 29 files of the shop (all files are sent in one
  response and loaded into the page).
