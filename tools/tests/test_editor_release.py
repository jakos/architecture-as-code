import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import editor_release
from editor_release import ReleaseError, release_tags

REPO = Path(__file__).resolve().parents[2]
PATCHES = REPO / "docker" / "editor" / "model-editor" / "patches"
IMAGE = "ghcr.io/jakos/likec4-model-editor"


@pytest.mark.parametrize(
    ("git_tag", "version", "minor"),
    [
        ("likec4-model-editor-v0.1.0", "0.1.0", "0.1"),
        ("likec4-model-editor-v1.12.3", "1.12.3", "1.12"),
        ("likec4-model-editor-v10.0.100", "10.0.100", "10.0"),
    ],
)
def test_release_tags_for_a_good_tag(git_tag, version, minor):
    release = release_tags(git_tag)
    assert release.version == version
    assert release.image == IMAGE
    assert release.refs == (f"{IMAGE}:{version}", f"{IMAGE}:{minor}")


@pytest.mark.parametrize(
    "git_tag",
    [
        "likec4-model-editor-v0.1",
        "likec4-model-editor-v0.1.0.1",
        "likec4-model-editor-0.1.0",
        "likec4-model-editor-v01.1.0",
        "likec4-model-editor-v0.1.0-rc1",
        "likec4-model-editor-v0.1.0+build",
        "other-v0.1.0",
        "v0.1.0",
        "likec4-v0.1.0",
        "likec4-model-editor-v1.59.4-1",
        "likec4-model-editor-v0.1.0\n",
        " likec4-model-editor-v0.1.0",
        "",
    ],
)
def test_release_tags_refuses_malformed_tags(git_tag):
    with pytest.raises(ReleaseError):
        release_tags(git_tag)


def test_cli_prints_github_output_lines(capsys):
    assert editor_release.main(["tags", "likec4-model-editor-v0.1.0"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert out == [
        "version=0.1.0",
        f"image={IMAGE}",
        f"ref={IMAGE}:0.1.0",
        f"tags={IMAGE}:0.1.0 {IMAGE}:0.1",
    ]


def test_cli_fails_on_a_bad_tag(capsys):
    assert editor_release.main(["tags", "likec4-model-editor-v0.1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.strip().splitlines()) == 1
    assert "likec4-model-editor-v0.1" in captured.err


def added_lines(patch: str) -> list[str]:
    return [
        line[1:]
        for line in patch.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    ]


def test_patches_name_the_product_and_credit_likec4():
    p1 = (PATCHES / "0001-remove-cloud-features.patch").read_text(encoding="utf-8")
    p3 = (PATCHES / "0003-editor-ui.patch").read_text(encoding="utf-8")
    assert any(line.strip() == "<title>LikeC4 Model Editor</title>" for line in added_lines(p1))

    header = p3.split("a/apps/playground/src/aac/AacHeader.tsx", 1)[1].split("diff --git", 1)[0]
    assert "LikeC4 Model Editor" in header
    assert "based on LikeC4" not in header

    about = p3.split("a/apps/playground/src/aac/AboutContent.tsx", 1)[1].split("diff --git", 1)[0]
    for text in (
        "Community project based on LikeC4, not affiliated with it.",
        "Denis",
        "Davydkov",
        "LICENSE-LikeC4.txt",
        "likec4.dev",
        "LICENSE.txt",
    ):
        assert text in about, text

    for patch in PATCHES.glob("*.patch"):
        for line in added_lines(patch.read_text(encoding="utf-8")):
            assert "Model editor" not in line, (patch.name, line)
            assert not re.search(r"LikeC4 Playground", line), (patch.name, line)
