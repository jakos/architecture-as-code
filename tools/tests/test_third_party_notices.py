"""Tests for tools/third_party_notices.py, on fake package trees under tmp_path."""

import json
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from third_party_notices import main

TITLE = "Test notices"


def make_package(
    parent: Path,
    name: str,
    version: str = "1.0.0",
    *,
    license: str | dict | None = "MIT",
    files: dict[str, str] | None = None,
    extra: dict | None = None,
) -> Path:
    """Create parent/<name>/package.json plus licence files; return the package directory."""
    directory = parent / name
    directory.mkdir(parents=True)
    data: dict = {"name": name, "version": version}
    if license is not None:
        data["license"] = license
    data.update(extra or {})
    (directory / "package.json").write_text(json.dumps(data), encoding="utf-8")
    for file, text in (files or {}).items():
        (directory / file).write_bytes(text.encode("utf-8"))
    return directory


def record(modules: Path, ids: list[str], name: str = "a.json") -> None:
    modules.mkdir(parents=True, exist_ok=True)
    (modules / name).write_text(json.dumps(ids), encoding="utf-8")


def run_bundle(modules: Path, out: Path) -> int:
    return main(["bundle", "--modules", str(modules), "--title", TITLE, "--out", str(out)])


def run_installed(root: Path, out: Path) -> int:
    return main(["installed", "--root", str(root), "--title", TITLE, "--out", str(out)])


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A pnpm-like layout: tree/node_modules/.pnpm/<id>/node_modules/<name>."""
    (tmp_path / "node_modules" / ".pnpm").mkdir(parents=True)
    return tmp_path


def pnpm_dir(tree: Path, ident: str) -> Path:
    path = tree / "node_modules" / ".pnpm" / ident / "node_modules"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_bundle_lists_each_package_once_with_its_licence_text(tree, tmp_path):
    react = make_package(
        pnpm_dir(tree, "react@19.0.0"),
        "react",
        "19.0.0",
        files={"LICENSE": "React licence text\r\nline two\r\n"},
        extra={"repository": {"url": "git+https://example.com/react.git"}},
    )
    out = tmp_path / "out" / "N.txt"
    record(
        tree / "mods",
        [
            (react / "index.js").as_posix(),
            (react / "cjs" / "react.js").as_posix(),
            (react / "index.js").as_posix(),
        ],
    )
    assert run_bundle(tree / "mods", out) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith(TITLE + "\n")
    assert text.count("Package: react@19.0.0") == 1
    assert "License: MIT" in text
    assert "Source: git+https://example.com/react.git" in text
    assert "--- LICENSE ---\nReact licence text\nline two\n" in text
    assert "Packages listed: 1" in text
    assert "\r" not in text


def test_bundle_uses_the_package_under_the_last_node_modules_segment(tree, tmp_path):
    outer = make_package(pnpm_dir(tree, "outer@1.0.0"), "outer", "1.0.0")
    inner = make_package(outer / "node_modules", "inner", "2.0.0", license="ISC")
    out = tmp_path / "N.txt"
    record(tree / "mods", [(inner / "lib" / "x.js").as_posix()])
    assert run_bundle(tree / "mods", out) == 0
    text = out.read_text(encoding="utf-8")
    assert "Package: inner@2.0.0" in text
    assert "Package: outer@" not in text
    assert "License: ISC" in text


def test_bundle_names_scoped_packages(tree, tmp_path):
    scoped = make_package(pnpm_dir(tree, "@mantine+core@8.0.0") / "@mantine", "core", "8.0.0")
    # The directory name is "core", the package.json name is "@mantine/core".
    (scoped / "package.json").write_text(
        json.dumps({"name": "@mantine/core", "version": "8.0.0", "license": "MIT"}),
        encoding="utf-8",
    )
    out = tmp_path / "N.txt"
    record(tree / "mods", [(scoped / "esm" / "index.mjs").as_posix()])
    assert run_bundle(tree / "mods", out) == 0
    assert "Package: @mantine/core@8.0.0" in out.read_text(encoding="utf-8")


def test_bundle_names_workspace_packages_without_an_entry(tree, tmp_path):
    react = make_package(pnpm_dir(tree, "react@19.0.0"), "react", "19.0.0")
    core = tmp_path / "packages" / "core"
    (core / "src").mkdir(parents=True)
    (core / "package.json").write_text(json.dumps({"name": "@likec4/core"}), encoding="utf-8")
    out = tmp_path / "N.txt"
    record(tree / "mods", [(react / "i.js").as_posix(), (core / "src" / "a.ts").as_posix()])
    assert run_bundle(tree / "mods", out) == 0
    text = out.read_text(encoding="utf-8")
    assert "LICENSE-LikeC4.txt: @likec4/core" in text
    assert "Package: @likec4/core" not in text
    assert text.count("Package: ") == 1


def test_bundle_ignores_virtual_ids_and_strips_queries(tree, tmp_path):
    react = make_package(pnpm_dir(tree, "react@19.0.0"), "react", "19.0.0")
    out = tmp_path / "N.txt"
    record(
        tree / "mods",
        [
            "\0vite/preload-helper",
            "virtual:something",
            "relative/path.js",
            (react / "index.js").as_posix() + "?v=123",
        ],
    )
    assert run_bundle(tree / "mods", out) == 0
    text = out.read_text(encoding="utf-8")
    assert text.count("Package: ") == 1
    assert "Package: react@19.0.0" in text


def test_bundle_fails_without_lists_or_without_third_party_packages(tree, tmp_path, capsys):
    out = tmp_path / "N.txt"
    assert run_bundle(tree / "missing", out) == 1
    assert "no module lists" in capsys.readouterr().err
    record(tree / "mods", ["\0virtual", "/work/packages/core/a.ts"])
    assert run_bundle(tree / "mods", out) == 1
    assert "no third-party package" in capsys.readouterr().err
    assert not out.exists()


def test_licence_and_notice_file_variants_are_included(tree, tmp_path):
    pkg = make_package(
        pnpm_dir(tree, "multi@1.0.0"),
        "multi",
        files={
            "LICENSE": "one",
            "LICENSE.md": "two",
            "LICENCE-MIT": "three",
            "COPYING": "four",
            "NOTICE": "five",
            "README.md": "not a licence",
        },
    )
    out = tmp_path / "N.txt"
    record(tree / "mods", [(pkg / "i.js").as_posix()])
    assert run_bundle(tree / "mods", out) == 0
    text = out.read_text(encoding="utf-8")
    for name in ("LICENSE", "LICENSE.md", "LICENCE-MIT", "COPYING", "NOTICE"):
        assert f"--- {name} ---" in text
    assert "README" not in text


def test_declared_licence_without_file_is_noted(tree, tmp_path):
    pkg = make_package(pnpm_dir(tree, "bare@1.0.0"), "bare", license="Apache-2.0")
    out = tmp_path / "N.txt"
    record(tree / "mods", [(pkg / "i.js").as_posix()])
    assert run_bundle(tree / "mods", out) == 0
    text = out.read_text(encoding="utf-8")
    assert "License: Apache-2.0" in text
    assert "No licence file in the package; the licence is as declared above." in text


def test_licence_declared_as_object_or_legacy_list(tree, tmp_path):
    a = make_package(pnpm_dir(tree, "a@1.0.0"), "a", license={"type": "BSD-3-Clause"})
    b = make_package(
        pnpm_dir(tree, "b@1.0.0"),
        "b",
        license=None,
        extra={"licenses": [{"type": "MIT"}, {"type": "Apache-2.0"}]},
    )
    out = tmp_path / "N.txt"
    record(tree / "mods", [(a / "i.js").as_posix(), (b / "i.js").as_posix()])
    assert run_bundle(tree / "mods", out) == 0
    text = out.read_text(encoding="utf-8")
    assert "License: BSD-3-Clause" in text
    assert "License: MIT OR Apache-2.0" in text


def test_package_without_licence_or_file_fails_naming_it(tree, tmp_path, capsys):
    pkg = make_package(pnpm_dir(tree, "nolicence@3.1.4"), "nolicence", "3.1.4", license=None)
    out = tmp_path / "N.txt"
    record(tree / "mods", [(pkg / "i.js").as_posix()])
    assert run_bundle(tree / "mods", out) == 1
    assert "nolicence@3.1.4" in capsys.readouterr().err
    assert not out.exists()


def test_installed_walks_nested_node_modules_and_skips_nameless_package_json(tmp_path, capsys):
    root = tmp_path / "likec4"
    modules = root / "node_modules"
    top = make_package(modules, "top", files={"LICENSE": "top licence"})
    (top / "dist").mkdir()
    (top / "dist" / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    nested = make_package(top / "node_modules", "nested", "2.0.0")
    make_package(nested / "node_modules", "deep", "3.0.0", license="ISC")
    make_package(modules / "@scope", "pkg", "4.0.0")
    (modules / "@scope" / "pkg" / "package.json").write_text(
        json.dumps({"name": "@scope/pkg", "version": "4.0.0", "license": "MIT"}),
        encoding="utf-8",
    )
    (modules / ".bin").mkdir()
    make_package(modules / ".bin", "hidden")
    out = tmp_path / "N.txt"
    assert run_installed(root, out) == 0
    text = out.read_text(encoding="utf-8")
    for label in ("top@1.0.0", "nested@2.0.0", "deep@3.0.0", "@scope/pkg@4.0.0"):
        assert f"Package: {label}" in text
    assert "hidden" not in text
    assert text.count("Package: ") == 4
    assert run_installed(tmp_path / "nothing", out) == 1
    assert "not found" in capsys.readouterr().err


def test_output_is_deterministic(tree, tmp_path):
    pkgs = [
        make_package(pnpm_dir(tree, f"p{i}@1.0.0"), f"p{i}", files={"LICENSE": f"text {i}"})
        for i in range(6)
    ]
    ids = [(p / "index.js").as_posix() for p in pkgs]
    first, second = tmp_path / "1.txt", tmp_path / "2.txt"
    record(tree / "mods", ids)
    assert run_bundle(tree / "mods", first) == 0
    shuffled = ids[:]
    random.Random(1).shuffle(shuffled)
    (tree / "mods" / "a.json").unlink()
    record(tree / "mods", shuffled[:3], "b.json")
    record(tree / "mods", shuffled[3:] + shuffled[:2], "a.json")
    assert run_bundle(tree / "mods", second) == 0
    assert first.read_bytes() == second.read_bytes()
    text = first.read_text(encoding="utf-8")
    assert text.index("Package: p0@") < text.index("Package: p5@")


def test_bundle_skips_nameless_package_json_when_naming_workspace_packages(tree, tmp_path):
    react = make_package(pnpm_dir(tree, "react@19.0.0"), "react", "19.0.0")
    core = tmp_path / "packages" / "core"
    (core / "src").mkdir(parents=True)
    (core / "package.json").write_text(json.dumps({"name": "@likec4/core"}), encoding="utf-8")
    (core / "src" / "package.json").write_text('{"type": "module"}', encoding="utf-8")
    out = tmp_path / "N.txt"
    record(tree / "mods", [(react / "i.js").as_posix(), (core / "src" / "a.ts").as_posix()])
    assert run_bundle(tree / "mods", out) == 0
    assert "LICENSE-LikeC4.txt: @likec4/core" in out.read_text(encoding="utf-8")


def test_bundle_rejects_a_module_list_that_is_not_an_array(tree, tmp_path, capsys):
    (tree / "mods").mkdir()
    (tree / "mods" / "a.json").write_text('{"modules": []}', encoding="utf-8")
    assert run_bundle(tree / "mods", tmp_path / "N.txt") == 1
    assert "is not a JSON array" in capsys.readouterr().err


def test_bundle_rejects_invalid_json_in_a_module_list(tree, tmp_path, capsys):
    (tree / "mods").mkdir()
    (tree / "mods" / "a.json").write_text("[not json", encoding="utf-8")
    assert run_bundle(tree / "mods", tmp_path / "N.txt") == 1
    assert "is not valid JSON" in capsys.readouterr().err


def test_bundle_rejects_a_recorded_package_without_name_or_version(tree, tmp_path, capsys):
    package = pnpm_dir(tree, "odd@1.0.0") / "odd"
    package.mkdir()
    (package / "package.json").write_text(json.dumps({"name": "odd"}), encoding="utf-8")
    record(tree / "mods", [(package / "i.js").as_posix()])
    assert run_bundle(tree / "mods", tmp_path / "N.txt") == 1
    assert "has no package.json with a name and version" in capsys.readouterr().err


def test_installed_fails_on_an_empty_node_modules(tmp_path, capsys):
    root = tmp_path / "likec4"
    (root / "node_modules").mkdir(parents=True)
    assert run_installed(root, tmp_path / "N.txt") == 1
    assert "no packages under" in capsys.readouterr().err
