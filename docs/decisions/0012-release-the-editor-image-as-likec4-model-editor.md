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
  tags (it accepts exactly that form). The workflow refuses a tag whose commit is not on `main`
  and a version whose `X.Y.Z` tag already exists in the registry. Pull requests that touch the
  image build it and check labels and licence files, without login or push.
- **Home.** Released from this repository for now (owner decision 2026-10-13); it may move to a
  separate repository later.
- **Licences.** The image carries LikeC4's licence (`LICENSE-LikeC4.txt`) and this repo's
  (`LICENSE.txt`), both served next to the app and linked from About; the Pages demo carries
  both too. LikeC4's MIT notice and copyright are kept.
- **Owner-only steps.** Creating and pushing the release tag, the first push to GHCR, and the
  package visibility are done by the owner, not by the workflow or an agent.

## Consequences

- A change to the patches or the Containerfile makes the image build and the Pages demo build
  (each about 11 minutes) run again once, in CI too.
- Nothing ties the image version to a LikeC4 upgrade automatically. Forgetting to bump minor on
  an upgrade is possible; the label, the README rule and the refusal to overwrite an existing
  `X.Y.Z` limit the damage.
- A package created by a workflow push starts private; the owner makes it public. The label
  `org.opencontainers.image.source` links the package to this repository. Both points are from
  memory of GitHub's behaviour and not checked against the docs on the day.
- The first real release is the first end-to-end test of `docker login` and the push with
  `GITHUB_TOKEN`.
- The static app bundles npm dependencies of the playground; their licence notices are not
  collected into the image (LikeC4's own image has the same situation). Worth a follow-up before
  wider distribution.
- Not checked: LikeC4's trademark or naming policy, and name collisions of `likec4-model-editor`
  on GitHub or GHCR.
- The image is a single-user, single-model server with HTTP Basic auth and defaults to
  `MODEL_PATH=examples/shop`. It must not be exposed to the internet as it is.
- Out of scope here: arm64, signing, SBOM and provenance, GitHub Releases, a `latest` tag.

## Sources

- GitHub docs on GHCR package visibility and linking a package to a repository with
  `org.opencontainers.image.source`: not checked (no network tool in this run); stated from
  memory.
- semver.org 2.0.0: not checked on the day; the scheme used is plain `MAJOR.MINOR.PATCH`.
