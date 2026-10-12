# 0010: The example site is published on GitHub Pages from `main`

Date: 2026-10-12 · Status: accepted

## Context

The repository is public. A browsable copy of the example model (`examples/shop`) is the
quickest way to show what the tooling produces and to try it without installing anything.
[ADR 0006](0006-likec4-is-the-tool-of-record.md) says browsing is the static site from
`likec4 build`; [ADR 0009](0009-readonly-viewer-main-on-push-branches-on-demand.md) added
`tools/viewer.py`, which already builds a site from a revision of the repo with the pinned image.

## Decision

- Only `examples/shop` is published, from `main`, on every push to `main`. The workflow
  `.github/workflows/pages.yml` runs `just pages-build HEAD`, which calls
  `tools/viewer.py pages` (the same export and `likec4 build` as the viewer, same pinned
  image), then uploads `build/pages` and deploys it with `actions/deploy-pages`.
- The site sits at the root of the Pages site (`https://jakos.github.io/architecture-as-code/`),
  not at `/main/` as in the self-hosted viewer. The base path is set once, in `justfile`
  (`pages_base`), so CI and `just pages-up` (http://127.0.0.1:8083/architecture-as-code/)
  build and serve the same thing.
- `/editor/` is reserved for the editor demo. `pages` replaces the whole output directory, so
  the editor build must write into `build/pages/editor/` after it.
- Pull requests run the build but do not upload or deploy.
- Token permissions are minimal: `contents: read` for the workflow, `pages: write` and
  `id-token: write` for the deploy job only. No secrets besides the built-in `GITHUB_TOKEN`.

## Consequences

- Pages is public. Only fictional or example models go there; real models in `workspaces/`
  stay off Pages.
- There are no branch or PR previews on Pages. The self-hosted viewer (ADR 0009) keeps that job.
- The site is stale while a deploy runs, and until the first deploy succeeds the link returns
  404. Pages must be enabled with source "GitHub Actions" in the repo settings first.
- `editor-hosting-and-auth` still owns self-hosted publishing, auth and versioned snapshots.

## Sources

- `actions/upload-pages-artifact` and `actions/deploy-pages` (latest releases v5.0.0 and
  v5.0.1 on 2026-10-12, read from the GitHub releases API).
