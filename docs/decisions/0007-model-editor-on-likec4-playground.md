# 0007: The model editor is the LikeC4 playground at a pinned tag plus our patch set

Date: 2026-10-11 · Status: accepted (owner approved the plan on 2026-10-11)

## Context

The editing path of Flow B1 needs a browser editor that someone without a local checkout can
use, with live feedback, backed by a git clone and ending in a `model/*` branch.

Two editors exist in this repo already:

- code-server with `likec4 start` (ADR 0005 trial): a full IDE, too much for the audience.
- the textarea page `tools/web_editor.html` ("not like last time, static buttons and forms",
  owner, 2026-10-11): a plain text area next to the diagram, no language support.

The owner prefers the feel of the LikeC4 playground editor ("I like feel of playground editor, I
would like to have all built on top of this code"). The playground (`apps/playground` of the
LikeC4 repo, MIT) is a React app with Monaco, the LikeC4 language server running in a Web Worker,
a live diagram and a Mantine UI. Its workspaces live in the browser (localStorage), and it
brings Share, a GitHub login and cloud playgrounds that need LikeC4's Cloudflare Worker.

Facts about the source, read at tag `v1.59.4` (commit
`33dbc2d34c399a99daf96e92fc28fe5d280a7fd5`), are in
[research/likec4-editor-image.md](../research/likec4-editor-image.md).

## Decision

- The model editor is `apps/playground` at the pinned tag `v1.59.4`, with an ordered **patch
  set** applied at image build time. The patches live in
  `docker/editor/model-editor/patches/`; the Containerfile checks the commit, applies them with
  `git apply` (the build fails if one does not apply), typechecks and builds. Look and feel,
  Monaco, the in-browser language server and the diagram are upstream's.
- The patches remove Share, the GitHub login, the cloud workspace menu, the examples and every
  call to the Worker, and the page makes no request outside its own origin. They add a file
  tree, save (Ctrl+S) and autosave to the server, Validate and Format with problems as editor
  markers, a branch indicator, a Submit modal and an About entry that says "based on LikeC4".
  New code is in new files (`apps/playground/src/aac/`); upstream files are changed as little as
  possible. The size is measured by `just playground-patches-stat` and recorded in the research
  doc.
- A patch set rather than a fork branch: everything stays in this repo and is reviewed with the
  rest of it, and no GitHub account is needed. `editor-image-release` can move the set into a
  fork later without changing what the patches do. A tag upgrade is `git apply --check` on the
  new tag; the README of the image says how.
- The server side is `tools/web_editor.py` behind a backend interface, **`ModelSource`**
  (`tools/model_source.py`): branch, list, read, write, changes, working directory and submit.
  `LocalCloneSource` is the only implementation today (a git clone on disk). `editor-git-backends`
  adds GitHub, GitLab and local-checkout sources by implementing the same protocol, and nothing
  else in the server touches git or the filesystem. Over HTTP it serves the built app (with Basic
  auth on every path) and the API: `GET /api/workspace`, file read and write, validate (with
  structured problems), format, status, submit.
- The model is loaded from the server and saved to the server. The browser keeps no model text:
  only the name of the open file is remembered in sessionStorage.
- The textarea page `likec4-web` is superseded by this editor. It stays, with its Compose
  profile, until a follow-up removes it.

## Consequences

- LikeC4's licence applies to the image: MIT, "based on LikeC4" in the About entry, and the
  licence text copied into the image. `editor-image-release` needs its own product name.
- Every LikeC4 bump costs a patch-set rebase. The patches avoid editing upstream files where a
  new file does the job, to keep that cost low; the upgrade trial in the research doc shows what
  it looked like for the newest tag available when this was written.
- Removed cloud features are unreferenced or deleted, not rewritten. Dead upstream files that
  nothing imports (for example `ShareButton.tsx`, the examples) stay in the source tree and are
  not part of the bundle. This is what keeps the patch small.
- The diagram is rendered in the browser from the files in the page, so there is no `likec4
  start` process and no `.snap` file is written (see [ADR 0008](0008-layout-snap-policy.md)).
- Browser checks of the UI are done by the orchestrator session with Playwright and are labelled
  as an AI stand-in; no real non-technical user has tried this editor yet.
- Risk: the language server needs every file loaded to resolve cross-file references. The editor
  loads all `.c4` files of the model into the page at start, which is fine for the shop model
  (29 files) and has not been tried at a larger size.
- Risk: the page relies on the browser sending the Basic auth credentials to same-origin
  worker and module requests. A session cookie is the fallback if a browser does not.
