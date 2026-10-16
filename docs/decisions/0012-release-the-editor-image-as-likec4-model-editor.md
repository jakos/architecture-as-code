# 0012: Release the editor image as LikeC4 Model Editor, with its own version, on GHCR

Date: 2026-10-13 · Status: accepted

## Context

The model editor image ([ADR 0007](0007-model-editor-on-likec4-playground.md)) is the LikeC4
playground at a pinned tag plus our patch set and server. It has only been built locally
(`localhost/aac-model-editor:v1.59.4`). To be usable outside this machine it needs a name, a
version, a registry and a repeatable release. The repository is public. The image holds LikeC4's
code (MIT, Copyright (c) 2023-2026 Denis Davydkov) and this repo's code (MIT, Copyright (c) 2026
Jakub Kostrzewa), so both notices must travel with it.

## Decision

- **Name.** The product is **LikeC4 Model Editor**; the slug (image name and release-tag prefix)
  is `likec4-model-editor`. Owner decision, 2026-10-13: LikeC4's name is in the product name by
  choice. LikeC4's logo is not used. To keep this from reading as an official LikeC4 product,
  the notice "Community project based on LikeC4, not affiliated with it." is shown in the About
  text, in the image description and in the READMEs.
- **Audience.** LikeC4 specifically, not generic C4. It is for people who want to use LikeC4 in
  this way, mainly non-technical contributors who propose architecture changes without knowing
  the git flow. This is said in the tagline, not in the name: "Edit a LikeC4 architecture model
  in the browser and propose changes for review, no git knowledge needed."
- **Header.** The app header shows the name alone; the About text keeps the LikeC4 credit, the
  version, the copyright line and both licence links.
- **Registry.** `ghcr.io/jakos/likec4-model-editor`, pushed by GitHub Actions with the
  workflow's own `GITHUB_TOKEN`. No stored credential.
- **Version.** The image has its own semantic version `X.Y.Z`, first release `0.1.0`, no
  pre-release or build suffix, immutable once pushed (owner decision 2026-10-13: not the
  LikeC4 version). Patch for fixes; minor for new features and for a LikeC4 upgrade; major for a
  breaking change of the run contract (environment variables, port, volume paths); while `0.x`
  a breaking change may bump minor.
- **Image tags.** Per release `X.Y.Z` and a moving `X.Y`. No `latest`.
- **LikeC4 version.** Recorded, not encoded in the version: the label
  `io.github.jakos.architecture-as-code.likec4-version`, the image description, the About text
  and a table in `docker/editor/model-editor/README.md`.
- **Release.** Pushing the git tag `likec4-model-editor-vX.Y.Z` runs
  `.github/workflows/editor-image.yml`. `tools/editor_release.py` maps the tag to version and
  tags (it accepts exactly that form, ASCII digits only). The workflow refuses a tag whose commit
  is not on `main`, a version whose `X.Y.Z` tag already exists in the registry, and an older patch
  than one already tagged for the same `X.Y` (the moving `X.Y` tag would go back). A registry
  error other than "not found" fails the job; it is never read as "not released". Pull requests that touch the
  image build it and check labels and licence files, without login or push.
- **Home.** Released from this repository for now (owner decision 2026-10-13); it may move to a
  separate repository later.
- **Licences.** The image carries LikeC4's licence (`LICENSE-LikeC4.txt`) and this repo's
  (`LICENSE.txt`), both served next to the app and linked from About; the Pages demo carries
  both too. LikeC4's MIT notice and copyright are kept. Every build also generates
  `THIRD-PARTY-NOTICES.txt` (the npm packages in the browser bundle, with licence texts; linked
  from About; the demo has its own) and, in the image, `THIRD-PARTY-NOTICES-likec4-cli.txt` (the
  npm tree of the installed `likec4` CLI), by `tools/third_party_notices.py` from what is bundled
  or installed.
- **Owner-only steps.** Creating and pushing the release tag, the first push to GHCR, and the
  package visibility are done by the owner, not by the workflow or an agent.

## Consequences

- A change to the patches or the Containerfile makes the image build and the Pages demo build
  (each about 11 minutes) run again once, in CI too.
- Nothing ties the image version to a LikeC4 upgrade automatically. Forgetting to bump minor on
  an upgrade is possible; the label, the README rule and the refusal to overwrite an existing
  `X.Y.Z` limit the damage.
- A package created by a workflow push starts private; the owner makes it public. The docs say
  "When you first publish a package, the default visibility is private." Publishing from a
  workflow with `GITHUB_TOKEN` links the workflow's repository automatically, and the label
  `org.opencontainers.image.source` links the package to this repository; a linked package
  inherits the repository's access permissions (not its visibility) by default. The docs warn
  that `GITHUB_TOKEN` cannot push if a package was earlier pushed to the same namespace and not
  connected to the repository. Checked 2026-10-15, no correction needed.
- The first real release is the first end-to-end test of `docker login` and the push with
  `GITHUB_TOKEN`.
- Licence notices are collected for the npm packages in the browser bundle and for the installed
  `likec4` CLI tree. Not collected: the base image's own notices (Node.js, Debian packages,
  Python), code that the `likec4` package bundles inside its own files, and any SBOM or licence
  policy check. A bundled package with neither a declared licence nor a licence file fails the
  build.
- Not checked: LikeC4's trademark or naming policy, and name collisions of `likec4-model-editor`
  on GitHub or GHCR.
- The image is a single-user, single-model server with HTTP Basic auth and defaults to
  `MODEL_PATH=examples/shop`. It must not be exposed to the internet as it is.
- Out of scope here: arm64, signing, SBOM and provenance, GitHub Releases, a `latest` tag.

## Sources

- Working with the Container registry (GitHub Docs),
  https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry,
  checked 2026-10-15: the default visibility of a first-published package is private;
  `GITHUB_TOKEN` publishes packages associated with the workflow repository; the label
  `org.opencontainers.image.source` connects a package to a repository.
- Configuring a package's access control and visibility (GitHub Docs),
  https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility,
  checked 2026-10-15: a package linked to a repository inherits that repository's access
  permissions (not its visibility) by default.
- Connecting a repository to a package (GitHub Docs),
  https://docs.github.com/en/packages/learn-github-packages/connecting-a-repository-to-a-package,
  checked 2026-10-15: `LABEL org.opencontainers.image.source=https://github.com/OWNER/REPO`
  connects the image to the repository.
- Semantic Versioning 2.0.0, https://semver.org/spec/v2.0.0.html, checked 2026-10-15: a normal
  version is `X.Y.Z` of non-negative integers without leading zeros; a pre-release suffix is
  optional. The scheme here is plain `MAJOR.MINOR.PATCH`, which the tag pattern in
  `tools/editor_release.py` enforces.
