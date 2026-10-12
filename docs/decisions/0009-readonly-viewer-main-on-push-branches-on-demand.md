# 0009: Read-only viewer; `main` built on push, branches and PRs on demand

Date: 2026-10-11 · Status: proposed

## Context

People who only read the architecture need a viewer that shows `main` by default and can show
a branch or a pull request when someone wants to review it. The editor
([ADR 0007](0007-model-editor-on-likec4-playground.md)) is a writable service and the wrong
thing to hand to readers. [ADR 0006](0006-likec4-is-the-tool-of-record.md) says browsing is the
static site from `likec4 build`, with no server.

Open questions this ADR answers: when to build which ref, and whether the LikeC4 image tags
are fixed.

## Decision

- The viewer is a separate, read-only service. It is nginx serving static `likec4 build`
  sites, nothing writable. This keeps ADR 0006's "no server".
- URLs: `main` at `/main/` (`/` redirects there, so `main` is the default), a local branch at
  `/branch/<name>/` (slashes in the name stay nested directories), a GitHub PR at `/pr/<n>/`,
  and a generated list of built refs at `/refs/`.
- Builds come from git commits (`git archive`), never from a working tree. A PR is fetched
  from `refs/pull/<n>/head` into `FETCH_HEAD`, so no ref in the host repo changes.
- `main` is built on every push to `main`.
- Branches and PRs are built on demand by a command (`just viewer-build <ref>`; later a CI
  trigger can call the same command). They are not built on every push. Reasons:
  - each build runs a 1.45 GB image and takes tens of seconds;
  - most branches are short-lived and nobody looks at their site;
  - preview sites that are rebuilt on every push but rarely read go stale or pile up.
- "On demand" means a command, not a button in the viewer. A build button would make the
  service writable and need authentication.
- Image tags are fixed: `docker.io/likec4/likec4:1.59.4` (shared with `validate`) and
  `docker.io/library/nginx:1.29.4-alpine`. The viewer adds no new pin.
- Sites use `--use-hash-history` and `--base /<path>/`, so views have deep links on a plain
  file server under a sub-path.

## Consequences

- Preview sites need cleanup. Nothing prunes `build/viewer/site/branch/` or `pr/` yet.
- Hosting, the publishing target, auth and the CI job (build `main` on push, optionally
  previews on PR events) are left to `editor-hosting-and-auth`. This change is the local tool
  (`tools/viewer.py`) and service (`docker/viewer/`) that job will call.
- The branch URL layout is `/branch/<name>/`. A branch `a` and a branch `a/b` cannot
  coexist in git, but over time (or through a bare-name ref such as `origin/main`) both can be
  asked for. The site of `a` contains the directory of `a/b`, so building `a` replaces it and
  drops `a/b` from `refs.json`. Building `a/b` while `a` is built is refused.
- A viewer only shows what was built: after a push to `main` the site is stale until the next
  build.

## Sources

- LikeC4 guide "Preview changes in PR" (`apps/docs/src/content/docs/guides/preview-changes-in-pr.mdx`
  at tag v1.59.4 in github.com/likec4/likec4): read on 2026-10-12; it is a draft page with a
  title and no content, so it gave no approach. The trigger (push, label, comment) stays open
  for `editor-hosting-and-auth`; the tool is trigger-agnostic.
- `likec4 build --help` (1.59.4): `--base`, `--use-hash-history`, `--title`.
