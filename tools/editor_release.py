"""Map a release git tag of LikeC4 Model Editor to its image version and image tags.

The model editor image (docker/editor/model-editor) is released as `likec4-model-editor` with
its own semantic version `X.Y.Z`. A release is a git tag `likec4-model-editor-vX.Y.Z`; the
release workflow (.github/workflows/editor-image.yml) pushes two image tags for it:

  ghcr.io/jakos/likec4-model-editor:X.Y.Z   immutable
  ghcr.io/jakos/likec4-model-editor:X.Y     moves to the newest patch of that minor

There is no `latest` tag. The LikeC4 version the image is built on is not part of the image
version; it is the image label io.github.jakos.architecture-as-code.likec4-version.

  tags <git-tag>
      prints `version=`, `image=`, `ref=` and `tags=` lines (usable with
      `>> "$GITHUB_OUTPUT"`). On a malformed tag it prints one line on stderr, nothing on
      stdout, and exits 1.

Run with `uv run --locked python tools/editor_release.py tags <git-tag>`. The tool never
builds, pushes, tags or uses the network.
"""

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass

NAME = "likec4-model-editor"
REGISTRY = "ghcr.io/jakos"

# Semantic version without pre-release or build suffix; no leading zeros.
_NUM = r"(0|[1-9]\d*)"
TAG_RE = re.compile(rf"^{re.escape(NAME)}-v{_NUM}\.{_NUM}\.{_NUM}$")


class ReleaseError(Exception):
    """The git tag is not a release tag."""


@dataclass(frozen=True)
class Release:
    version: str
    image: str
    refs: tuple[str, str]  # X.Y.Z (immutable), X.Y (moving)


def release_tags(git_tag: str) -> Release:
    match = TAG_RE.fullmatch(git_tag)
    if match is None:
        raise ReleaseError(
            f"not a release tag: {git_tag!r} (expected {NAME}-vX.Y.Z, for example {NAME}-v0.1.0)"
        )
    major, minor, patch = match.groups()
    image = f"{REGISTRY}/{NAME}"
    return Release(
        version=f"{major}.{minor}.{patch}",
        image=image,
        refs=(f"{image}:{major}.{minor}.{patch}", f"{image}:{major}.{minor}"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    tags_cmd = sub.add_parser(
        "tags", help="print version, image and image tags for a release git tag"
    )
    tags_cmd.add_argument("git_tag")
    args = parser.parse_args(argv)

    try:
        release = release_tags(args.git_tag)
    except ReleaseError as err:
        print(f"editor_release: {err}", file=sys.stderr)
        return 1
    print(f"version={release.version}")
    print(f"image={release.image}")
    print(f"ref={release.refs[0]}")
    print(f"tags={' '.join(release.refs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
