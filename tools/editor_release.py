"""Map a release git tag of LikeC4 Model Editor to its image version and image tags.

The model editor image (docker/editor/model-editor) is released as `likec4-model-editor` with
its own semantic version `X.Y.Z`. A release is a git tag `likec4-model-editor-vX.Y.Z`; the
release workflow (.github/workflows/editor-image.yml) pushes two image tags for it:

  ghcr.io/jakos/likec4-model-editor:X.Y.Z   immutable
  ghcr.io/jakos/likec4-model-editor:X.Y     moves to the newest patch of that minor

There is no `latest` tag. The LikeC4 version the image is built on is not part of the image
version; it is the image label io.github.jakos.architecture-as-code.likec4-version.

  tags <git-tag> [--released TAG ...]
      prints `version=`, `image=`, `ref=` and `tags=` lines (usable with
      `>> "$GITHUB_OUTPUT"`). On a malformed tag it prints one line on stderr, nothing on
      stdout, and exits 1. `--released` lists the release tags that already exist in git; a
      tag with a lower patch than one of them in the same X.Y is refused, because the moving
      X.Y tag would go back to an older patch. Entries that are not release tags are ignored.

  check-unreleased <ref> --inspect-exit N
      reads the output of `docker manifest inspect <ref>` from stdin and the exit code N of
      that command. Exits 0 only when the registry said the manifest or name is unknown.
      Exits 1 with one line on stderr when the version already exists, and also when the
      check failed for any other reason (network, auth, server error): an error is never
      read as "not released".

Run with `uv run --locked python tools/editor_release.py tags <git-tag>`. The tool never
builds, pushes, tags or uses the network; the workflow gathers the input.
"""

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

NAME = "likec4-model-editor"
REGISTRY = "ghcr.io/jakos"

# Semantic version without pre-release or build suffix; no leading zeros. ASCII digits only
# (`\d` would accept other Unicode digits).
_NUM = r"(0|[1-9][0-9]*)"
TAG_RE = re.compile(rf"^{re.escape(NAME)}-v{_NUM}\.{_NUM}\.{_NUM}$")


class ReleaseError(Exception):
    """The git tag is not a release tag."""


@dataclass(frozen=True)
class Release:
    version: str
    image: str
    refs: tuple[str, str]  # X.Y.Z (immutable), X.Y (moving)


def release_tags(git_tag: str, released: Iterable[str] = ()) -> Release:
    match = TAG_RE.fullmatch(git_tag)
    if match is None:
        raise ReleaseError(
            f"not a release tag: {git_tag!r} (expected {NAME}-vX.Y.Z, for example {NAME}-v0.1.0)"
        )
    major, minor, patch = match.groups()
    for other in released:
        other_match = TAG_RE.fullmatch(other)
        if other_match is None:
            continue
        o_major, o_minor, o_patch = other_match.groups()
        if (o_major, o_minor) == (major, minor) and int(o_patch) > int(patch):
            raise ReleaseError(
                f"{git_tag} is an older patch than the already tagged {other}; the moving "
                f"{major}.{minor} tag would go back to an older patch. Bump the version."
            )
    image = f"{REGISTRY}/{NAME}"
    return Release(
        version=f"{major}.{minor}.{patch}",
        image=image,
        refs=(f"{image}:{major}.{minor}.{patch}", f"{image}:{major}.{minor}"),
    )


_NOT_FOUND = ("no such manifest", "manifest unknown", "name unknown")


def check_unreleased(ref: str, inspect_exit: int, inspect_output: str) -> None:
    """Raise ReleaseError unless `docker manifest inspect <ref>` showed the ref is unknown."""
    if inspect_exit == 0:
        raise ReleaseError(
            f"{ref} already exists; a released version is never overwritten. Bump the version."
        )
    lowered = inspect_output.lower()
    if any(text in lowered for text in _NOT_FOUND):
        return
    first = next((ln.strip() for ln in inspect_output.splitlines() if ln.strip()), "no output")
    raise ReleaseError(
        f"could not tell whether {ref} exists (docker manifest inspect exit {inspect_exit}): "
        f"{first}; refusing to release"
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
    tags_cmd.add_argument(
        "--released", nargs="*", default=[], metavar="TAG", help="release tags that exist in git"
    )
    unreleased_cmd = sub.add_parser(
        "check-unreleased", help="decide from `docker manifest inspect` output whether to go on"
    )
    unreleased_cmd.add_argument("ref")
    unreleased_cmd.add_argument("--inspect-exit", type=int, required=True)
    args = parser.parse_args(argv)

    if args.command == "check-unreleased":
        try:
            check_unreleased(args.ref, args.inspect_exit, sys.stdin.read())
        except ReleaseError as err:
            print(f"editor_release: {err}", file=sys.stderr)
            return 1
        return 0

    try:
        release = release_tags(args.git_tag, args.released)
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
