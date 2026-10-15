"""Generate the third-party licence notices of the model editor image at build time.

Runs inside the image build with the image's own `python3` (3.13), standard library only:

  bundle --modules DIR --title TEXT --out FILE
      DIR holds JSON arrays of module ids (source file paths) that the Vite build recorded.
      Writes the name, version, declared licence, source and licence texts of every npm package
      whose files went into the bundle. Code outside node_modules is LikeC4's own workspace
      code; its package names are listed in the header and get no entry.
  installed --root PACKAGE_DIR --title TEXT --out FILE
      Same for every package under PACKAGE_DIR/node_modules, at any depth (an npm install tree).

The output depends only on its input (no timestamps), so two runs give identical files. A
package with neither a declared licence nor a licence file makes the command fail: there is
no exception list. Exit code 1 and one line on stderr on any error.
"""

import argparse
import json
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

LICENCE_PREFIXES = ("license", "licence", "copying", "notice")
SEPARATOR = "=" * 78
NO_FILE_LINE = "No licence file in the package; the licence is as declared above."
NOT_STATED = "not stated"


class NoticeError(Exception):
    """A problem worth one line on stderr."""


@dataclass(frozen=True)
class Package:
    name: str
    version: str
    directory: Path


def read_package_json(directory: Path) -> dict | None:
    path = directory / "package.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError as err:
        raise NoticeError(f"{path.as_posix()} is not valid JSON: {err}") from err
    return data if isinstance(data, dict) else None


def package_of(directory: Path) -> Package | None:
    """The package in `directory`, or None if its package.json lacks a name or version."""
    data = read_package_json(directory)
    if data is None:
        return None
    name, version = data.get("name"), data.get("version")
    if not isinstance(name, str) or not isinstance(version, str) or not name or not version:
        return None
    return Package(name, version, directory)


def declared_licence(data: dict) -> str:
    value = data.get("license")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict) and isinstance(value.get("type"), str) and value["type"].strip():
        return value["type"].strip()
    legacy = data.get("licenses")
    if isinstance(legacy, list):
        types = []
        for item in legacy:
            kind = item.get("type") if isinstance(item, dict) else item
            if isinstance(kind, str) and kind.strip():
                types.append(kind.strip())
        if types:
            return " OR ".join(types)
    return NOT_STATED


def source_of(data: dict) -> str:
    repo = data.get("repository")
    url = repo.get("url") if isinstance(repo, dict) else repo
    if isinstance(url, str) and url.strip():
        return url.strip()
    home = data.get("homepage")
    if isinstance(home, str) and home.strip():
        return home.strip()
    return NOT_STATED


def licence_files(directory: Path) -> list[Path]:
    files = [
        p
        for p in directory.iterdir()
        if p.is_file() and p.name.lower().startswith(LICENCE_PREFIXES)
    ]
    return sorted(files, key=lambda p: p.name)


def entry(package: Package) -> str:
    data = read_package_json(package.directory) or {}
    licence = declared_licence(data)
    files = licence_files(package.directory)
    label = f"{package.name}@{package.version}"
    if licence == NOT_STATED and not files:
        raise NoticeError(f"{label} states no licence and ships no licence file")
    lines = [SEPARATOR, f"Package: {label}", f"License: {licence}", f"Source: {source_of(data)}"]
    if not files:
        lines += ["", NO_FILE_LINE]
    for file in files:
        text = file.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        lines += ["", f"--- {file.name} ---", text.rstrip("\n")]
    return "\n".join(lines) + "\n"


def render(title: str, origin: str, packages: Iterable[Package], extra: list[str]) -> str:
    unique = sorted(
        {(p.name, p.version): p for p in packages}.values(), key=lambda p: (p.name, p.version)
    )
    head = [
        title,
        "",
        f"Generated at build time by tools/third_party_notices.py from {origin}.",
        f"Packages listed: {len(unique)}",
        *extra,
        "",
    ]
    return "\n".join(head) + "\n" + "\n".join(entry(p) for p in unique)


def module_paths(modules_dir: Path) -> list[str]:
    lists = sorted(modules_dir.glob("*.json")) if modules_dir.is_dir() else []
    if not lists:
        raise NoticeError(f"no module lists (*.json) in {modules_dir.as_posix()}")
    paths: list[str] = []
    for file in lists:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise NoticeError(f"{file.as_posix()} is not valid JSON: {err}") from err
        if not isinstance(data, list):
            raise NoticeError(f"{file.as_posix()} is not a JSON array")
        paths.extend(item for item in data if isinstance(item, str))
    return paths


def clean_id(raw: str) -> PurePosixPath | None:
    """The absolute source path in a module id, or None for virtual ids and relative ones."""
    if raw.startswith("\0"):
        return None
    raw = raw.split("?", 1)[0].replace("\\", "/")
    is_absolute = raw.startswith("/") or (len(raw) > 2 and raw[1] == ":" and raw[2] == "/")
    return PurePosixPath(raw) if is_absolute else None


def split_module(path: PurePosixPath) -> tuple[PurePosixPath | None, PurePosixPath]:
    """(package directory under the last node_modules or None, the path)."""
    parts = path.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] != "node_modules":
            continue
        rest = parts[i + 1 :]
        if not rest:
            return None, path
        size = 2 if rest[0].startswith("@") else 1
        if len(rest) < size:
            return None, path
        return PurePosixPath(*parts[: i + 1 + size]), path
    return None, path


def workspace_name(path: PurePosixPath) -> str | None:
    for parent in path.parents:
        data = read_package_json(Path(parent))
        if data is not None:
            name = data.get("name")
            if isinstance(name, str) and name:
                return name
    return None


def bundle(modules_dir: Path, title: str) -> str:
    third: dict[PurePosixPath, None] = {}
    workspace: set[str] = set()
    for raw in module_paths(modules_dir):
        path = clean_id(raw)
        if path is None:
            continue
        package_dir, _ = split_module(path)
        if package_dir is not None:
            third[package_dir] = None
        else:
            name = workspace_name(path)
            if name:
                workspace.add(name)
    packages = []
    for directory in third:
        package = package_of(Path(directory))
        if package is None:
            raise NoticeError(f"{directory.as_posix()} has no package.json with a name and version")
        packages.append(package)
    if not packages:
        raise NoticeError("the module lists name no third-party package")
    extra = []
    if workspace:
        extra = [
            "LikeC4 workspace packages bundled as source are covered by LICENSE-LikeC4.txt: "
            + ", ".join(sorted(workspace))
        ]
    return render(title, "the modules bundled into the app", packages, extra)


def installed(root: Path, title: str) -> str:
    base = root / "node_modules"
    if not base.is_dir():
        raise NoticeError(f"{base.as_posix()} not found")
    packages: list[Package] = []
    stack = [base]
    while stack:
        current = stack.pop()
        for child in sorted(current.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if child.name.startswith("@") and current.name == "node_modules":
                stack.append(child)
                continue
            package = package_of(child)
            if package is not None:
                packages.append(package)
            nested = child / "node_modules"
            if nested.is_dir():
                stack.append(nested)
    if not packages:
        raise NoticeError(f"no packages under {base.as_posix()}")
    return render(title, f"the packages installed under {root.name}/node_modules", packages, [])


def write(out: Path, text: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(text.encode("utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("bundle", help="notices for the modules a build recorded")
    b.add_argument("--modules", required=True, type=Path)
    i = sub.add_parser("installed", help="notices for an installed npm package tree")
    i.add_argument("--root", required=True, type=Path)
    for p in (b, i):
        p.add_argument("--title", required=True)
        p.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "bundle":
            text = bundle(args.modules, args.title)
        else:
            text = installed(args.root, args.title)
        write(args.out, text)
    except (NoticeError, OSError) as err:
        print(f"third_party_notices: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
