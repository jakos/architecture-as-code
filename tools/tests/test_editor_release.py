import io
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
        "likec4-model-editor-v1.\u0663.0",
        "likec4-model-editor-v\uff11.0.0",
        "likec4-model-editor-v1.1\u0663.0",
        "likec4-model-editor-v1\uff11.0.0",
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


TAG = "likec4-model-editor-v"


def test_release_tags_refuses_an_older_patch_than_released():
    with pytest.raises(ReleaseError, match="older patch"):
        release_tags(f"{TAG}0.1.0", released=[f"{TAG}0.1.1"])


def test_release_tags_allows_other_minors_and_itself():
    released = [
        f"{TAG}0.1.5",
        f"{TAG}0.1.4",
        f"{TAG}0.2.0",
        f"{TAG}1.0.0",
        "v9.9.9",
        f"{TAG}0.1.99-rc1",
    ]
    assert release_tags(f"{TAG}0.1.5", released=released).version == "0.1.5"


def test_cli_refuses_an_older_patch(capsys):
    argv = ["tags", f"{TAG}0.1.0", "--released", f"{TAG}0.1.0", f"{TAG}0.1.2"]
    assert editor_release.main(argv) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.strip().splitlines()) == 1


REF = f"{IMAGE}:0.1.0"


def test_check_unreleased_refuses_an_existing_version():
    with pytest.raises(ReleaseError, match="already exists"):
        editor_release.check_unreleased(REF, 0, "{}")


@pytest.mark.parametrize(
    "output",
    [
        f"no such manifest: {REF}",
        "manifest unknown: manifest unknown",
        "errors:\nname unknown: repository name not known to registry",
        "No Such Manifest: x",
    ],
)
def test_check_unreleased_accepts_not_found(output):
    editor_release.check_unreleased(REF, 1, output)


@pytest.mark.parametrize(
    "output",
    [
        "unauthorized: authentication required",
        "denied: requested access to the resource is denied",
        'Get "https://ghcr.io/v2/": dial tcp: lookup ghcr.io: i/o timeout',
        "received unexpected HTTP status: 500 Internal Server Error",
        "",
    ],
)
def test_check_unreleased_fails_on_other_errors(output):
    with pytest.raises(ReleaseError, match="could not tell"):
        editor_release.check_unreleased(REF, 1, output)


def test_cli_check_unreleased_accepts_not_found(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"no such manifest: {REF}\n"))
    assert editor_release.main(["check-unreleased", REF, "--inspect-exit", "1"]) == 0
    assert capsys.readouterr().err == ""


def test_cli_check_unreleased_refuses_an_error(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("unauthorized: authentication required\n"))
    assert editor_release.main(["check-unreleased", REF, "--inspect-exit", "1"]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.strip().splitlines()) == 1


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
