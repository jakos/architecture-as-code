# LikeC4 Model Editor

Edit a LikeC4 architecture model in the browser and propose changes for review, no git knowledge needed.

Community project based on LikeC4, not affiliated with it.

The browser editor of Flow B1 ([ADR 0007](../../../docs/decisions/0007-model-editor-on-likec4-playground.md)):
the LikeC4 playground (`apps/playground`) at a pinned tag, plus the patch set in `patches/`,
served by `tools/web_editor.py` on a git clone of the model.

It is for LikeC4 specifically (not generic C4), and mainly for non-technical contributors who
propose architecture changes without knowing the git flow
([ADR 0012](../../../docs/decisions/0012-release-the-editor-image-as-likec4-model-editor.md)).

Based on [LikeC4](https://likec4.dev), MIT licence, Copyright (c) 2023-2026 Denis Davydkov.
The image carries both licence texts: LikeC4's
(`/usr/local/share/model-editor/LICENSE-LikeC4.txt`) and this repo's MIT licence
(`/usr/local/share/model-editor/LICENSE.txt`, Copyright (c) 2026 Jakub Kostrzewa). The editor's
About entry carries the notice above and links both. LikeC4's logo is not used. Everything this
repo adds (the patches, the server) is this repo's code.

| What | Where |
| --- | --- |
| Pin: tag `v1.59.4`, commit `33dbc2d34c399a99daf96e92fc28fe5d280a7fd5` | `Containerfile` (`ARG LIKEC4_TAG`, `ARG LIKEC4_COMMIT`, before the first `FROM`, the only place with a default) |
| Release workflow, tag-to-version helper | `.github/workflows/editor-image.yml`, `tools/editor_release.py` |
| Patch set, applied in file-name order | `patches/` |
| Server, backend interface, submit | `tools/web_editor.py`, `tools/model_source.py`, `tools/submit.py` |
| Patch tool (size, regenerate) | `tools/playground_patches.py` |
| Compose service (port 8097) | `docker/compose.editor.yml`, service `editor-model-editor` |
| Static demo for GitHub Pages | `Containerfile` stages `demo-build` and `demo`, `tools/editor_demo.py` |

## Build and run

```
just model-editor-build        # needs GitHub and npm, takes minutes
just poc-remote                # local bare remote build/poc-remote.git
just editor-up model-editor    # needs PASSWORD, MODEL_USER, MODEL_SLUG (see .env.example)
just editor-down
```

The page is http://127.0.0.1:8097 (HTTP Basic auth: any user name, the `PASSWORD`). The container
clones the remote on a branch `model/<MODEL_USER>/<date>-<MODEL_SLUG>`; Submit sends only that
branch. No password or token is in the image.

## Release

The image is released as `ghcr.io/jakos/likec4-model-editor` with its own version, not the
LikeC4 version ([ADR 0012](../../../docs/decisions/0012-release-the-editor-image-as-likec4-model-editor.md)).

- A release is the git tag `likec4-model-editor-vX.Y.Z`, for example `likec4-model-editor-v0.1.0`
  (first release `0.1.0`), pushed on a commit that is on `main`. The workflow
  `.github/workflows/editor-image.yml` builds the image with `--build-arg IMAGE_VERSION=X.Y.Z`
  and pushes the tags `X.Y.Z` (immutable) and `X.Y` (newest patch of that minor). There is no
  `latest`. It refuses a malformed tag, a commit that is not on `main` and a version that is
  already in the registry.
- Semantic versioning: patch for fixes; minor for new features and for a LikeC4 upgrade; major
  for a breaking change of the run contract (environment variables, port, volume paths). While
  the version is `0.x`, a breaking change may bump minor instead.
- `just editor-release-tags likec4-model-editor-v0.1.0` shows what a tag maps to (version, image,
  image tags) without building or publishing anything.
- Pull requests that touch the image build it and check the labels and licence files; they do
  not log in or push.
- Owner steps, never done by the workflow or a task: create and push the release tag; make the
  package public (a package created by a workflow push starts private; the label
  `org.opencontainers.image.source` links it to this repo); the first release is the first time
  `docker login` and the push with the workflow's `GITHUB_TOKEN` run for real.
- Labels: `org.opencontainers.image.title`, `.description` (the tagline and the notice),
  `.source`, `.licenses` (`MIT`), `.version` (the image version; `dev` for a local build) and
  `io.github.jakos.architecture-as-code.likec4-version` (the LikeC4 version the image is built
  on, for example `1.59.4`). Find it with
  `podman image inspect --format '{{index .Config.Labels "io.github.jakos.architecture-as-code.likec4-version"}}' <image>`.

Run a published image (single user, single model, HTTP Basic auth: do not expose it to the
internet as it is; `MODEL_PATH` defaults to `examples/shop`, set it to the model directory in
your repository):

```
podman run --rm -p 8097:8080 \
  -e REPO_URL=<remote of the model repo> -e MODEL_PATH=<model directory in the repo> \
  -e PASSWORD=<password> -e MODEL_USER=<your name> -e MODEL_SLUG=<short topic> \
  ghcr.io/jakos/likec4-model-editor:0.1
```

The server listens on port 8080 in the container. The module docstring of
`docker/editor/entrypoint.py` lists all environment variables.

LikeC4 version per release (filled in when a release is made; none yet):

| Release | LikeC4 |
| --- | --- |
| (none yet) | v1.59.4 is what `main` builds on |

## What the patches do

| Patch | Change |
| --- | --- |
| `0001-remove-cloud-features.patch` | Deletes the share routes and the GitHub redirect route, drops the CDN font links, the LikeC4 favicon and meta tags from `index.html`, sets a system font fallback for Monaco, removes the examples from `usePlayground.ts`. The Share, Login and Playgrounds components stay in the tree but nothing imports them, so they are not in the bundle. |
| `0002-server-workspace.patch` | `playground-machine.ts`: the localStorage write becomes a save to the server and the autosave delay is 800 ms; the share actor is a stub that fails. New `src/aac/server.ts` (same-origin API client) and `src/aac/saving.ts` (save state, queue, retry). Demo mode, data side: new `src/aac/mode.ts` (`DEMO`, true in the Vite mode `demo`); in a demo build `server.ts` reads `workspace.json` and `saving.ts` never writes. |
| `0003-editor-ui.patch` | The workspace route loads all files from `GET /api/workspace` and shows the file tree, the file bar, the problems list and our header. New files in `src/aac/` (header, file tree, Submit dialog, About, problems and markers). `routes/index.tsx` opens the workspace. A click on a file in the tree also switches the diagram to the file's view (`src/aac/followFile.ts`: the first view defined in the file, else the first scoped or including view of the first element or deployment node it defines, else nothing; asked from the language server's Locate request and the model, no names built in). For that, 0003 adds a few lines to `src/monaco/LanguageClientSync.tsx` that hand the language client's Locate request to `src/aac/language.ts`. Demo mode, UI side: the route loads the workspace through `loadWorkspace()`, the header shows the demo label and the repo link instead of the branch, the save indicator and Validate, Format and Submit, and `src/router.tsx` (new in this patch) uses hash history. |

Why 0002 and 0003 are split that way (and 0001 too): a patch holds whole files, so each step
compiles on its own. `just playground-patches-stat` prints the size.

## Demo build (GitHub Pages)

The same app, built in the Vite mode `demo`, is published at `/editor/` of the Pages site
([ADR 0011](../../../docs/decisions/0011-editor-demo-on-github-pages.md)). It has no server:
the model is a `workspace.json` next to `index.html`, edits stay in memory and are never saved,
and a reload resets them.

```
just editor-demo-app           # needs GitHub and npm, takes minutes; output: build/editor-demo-app
just pages-build HEAD          # the viewer at the root of build/pages (replaces all of it)
just editor-demo-assemble HEAD # app + workspace.json -> build/pages/editor
just pages-up                  # serves build/pages on http://127.0.0.1:8083/architecture-as-code/
```

- `editor-demo-app` builds the stage `demo` of the Containerfile (`FROM build AS demo-build`, so
  the commit check and the patches are the same as for the image) with
  `vite build --mode demo --base /architecture-as-code/editor/`. The base comes from `pages_base`
  in the `justfile` and is passed as the build-arg `DEMO_BASE`. The files are copied out of the
  image with `create`, `cp` and `rm`.
- `workspace.json` is `{"files": {"<path>": "<text>"}}`: the `.c4` files of `examples/shop` at a git
  ref (`editor-demo-assemble ref`, default `main`), as committed. `pages-up` adds the demo only
  when the app was built.
- Both steps check the files before they are published: `index.html` refers only to paths under the
  base, there is no Python file, and no file contains a path of the server API (`/api/workspace`,
  `/api/file`, `/api/status`, `/api/validate`, `/api/format`, `/api/submit`).
- The URL is a hash URL (`.../editor/#/w/model/...`), so a reload works on a host without a
  fallback to `index.html`.
- Hidden in the demo: the branch badge, the save indicator, Validate, Format and Submit. Ctrl+S
  does nothing and leaving the page never asks. The language server in the browser still shows
  errors, completion and hover.
- CI (`.github/workflows/pages.yml`) caches `build/editor-demo-app` on a hash of the Containerfile,
  the patches, `tools/editor_demo.py`, `tools/viewer.py` and the `justfile`.

## Change the patches

```
git clone --depth 1 --branch v1.59.4 https://github.com/likec4/likec4.git build/likec4-src
# edit build/likec4-src/apps/playground (new code goes in src/aac/)
uv run --locked python tools/playground_patches.py export build/likec4-src docker/editor/model-editor/patches
just playground-patches-stat
```

`export` stages the clone's changes (`git add -A` in the clone) and rewrites the patch files from
`git diff` against the tag. It never commits anywhere. A changed file that no patch claims is an
error: add it to `PATCH_PATHS` in the tool. To check the typescript before a long image build, run
`pnpm install --filter '@likec4/playground...'` and `pnpm run typecheck` in the clone, or build the
image (the Containerfile runs `pnpm run typecheck`).

## Upgrade LikeC4

1. Pick the new tag. Bump together: the global `ARG LIKEC4_TAG` and `ARG LIKEC4_COMMIT` in the
   `Containerfile` (one place; the stages only redeclare them), `likec4_image` in the
   `justfile`, `IMAGE` in `tools/validate_models.py`, the other two editor Containerfiles, and
   the image tag in the `justfile` and Compose file.
2. Check the patches without building anything:

   ```
   git clone --depth 1 --branch <new tag> https://github.com/likec4/likec4.git /tmp/likec4-new
   cd /tmp/likec4-new && for p in <repo>/docker/editor/model-editor/patches/*.patch; do git apply --check "$p"; done
   ```

3. For a rejected hunk, apply the patch by hand in a clone of the new tag, fix the conflict, and
   regenerate with `export` as above. Typecheck, run `just model-editor-build` and the browser
   checks again.

A LikeC4 upgrade is released as a new minor version of the image (see Release).

`docs/research/likec4-editor-image.md` records the trial that was done for v1.59.4.

## Limits

- The editor opens and edits existing `.c4` files; it does not create, rename or delete them.
- It shows an automatic layout and does not read or write `.snap` files
  ([ADR 0008](../../../docs/decisions/0008-layout-snap-policy.md)).
- One user and one model per container; sign-in, branch and source pickers are not here
  (`editor-git-backends`, `editor-hosting-and-auth`).
