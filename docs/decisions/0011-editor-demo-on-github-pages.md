# 0011: A demo of the model editor on GitHub Pages, edits not saved

Date: 2026-10-13 · Status: accepted

## Context

[ADR 0010](0010-example-site-on-github-pages.md) publishes the example model as a read-only
site and reserves `/editor/`. The model editor
([ADR 0007](0007-model-editor-on-likec4-playground.md)) needs a server: it reads and writes
the files of a git clone. A visitor cannot try it without a container. The LikeC4 playground
that the editor is built from runs in the browser alone, and our patches added the server on top.

GitHub Pages has no server code and no fallback to `index.html` for unknown paths.

## Decision

- The demo is the same app as the editor image, built a second time in the Vite mode `demo`
  (`vite build --mode demo --base /architecture-as-code/editor/`). Server mode stays the default.
  The mode is a constant (`src/aac/mode.ts`), so the demo bundle holds none of the server API
  calls.
- The demo code is in the existing patches 0002 (data side: static workspace loader, no saving)
  and 0003 (UI side: header, route loader, hash history). No fourth patch: a patch holds whole
  files and those files are already owned by 0002 and 0003.
- The model is a `workspace.json` next to `index.html`, written by `tools/editor_demo.py
  assemble` from the committed `.c4` files of `examples/shop` at a git ref, never from the
  working tree. It is not part of the app build, so a model change only re-runs the fast step.
- The router uses hash history (`.../editor/#/w/model/...`), so a reload of a deep link does
  not hit a 404 on Pages.
- Nothing is saved: edits live in memory, a reload resets the text, and nothing but the name of
  the open file is put into sessionStorage. The header says `Demo – changes are not saved`,
  links to the repo, and has no branch badge, save indicator, Validate, Format or Submit. The
  language server in the browser still shows errors, completion and hover.
- The app is built from a new stage of the model editor's Containerfile that starts from the
  `build` stage, so the commit check and the patches are not repeated. `tools/editor_demo.py
  app` extracts the files, and a bundle check refuses to publish files that refer to another
  origin or to a path outside the base, hold Python, or contain a path of the editor server's API.
- In CI the app (about 11 minutes cold) is cached with `actions/cache` on a hash of the
  Containerfile, the patches, the two tools and the justfile. Pull requests build it too; the
  upload and deploy stay on `main` with the permissions of ADR 0010.
- Examples only (`examples/shop`), as in ADR 0010.

## Consequences

- A change to a patch, the Containerfile, either tool or the justfile makes one Pages run
  about 11 minutes longer, on pull requests too. The justfile is in the key on purpose, although
  it is coarse: the base path lives there.
- Every LikeC4 upgrade needs the demo built and looked at as well as the image.
- The demo cannot Validate or Format; a browser-only version needs new wiring into the problems
  panel and is not planned.
- The URLs are hash URLs, unlike the editor image.
- Creating, renaming and deleting files, and share links, are not in the demo, as in the editor.

## Sources

- `actions/cache` latest release v6.1.0 (2026-06-26), read from the GitHub releases API on
  2026-10-13.
