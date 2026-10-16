"""Measure and regenerate the model editor's patch set against the LikeC4 playground.

The model editor is the LikeC4 playground (apps/playground at a pinned tag) plus the ordered
patches in docker/editor/model-editor/patches/. This tool

  stat <patch dir>              size of the patch set from the diff headers (no network, no repo)
  export <src clone> <patch dir>   rewrite the patches from changes made in a clone of the tag

Run with `uv run --locked python tools/playground_patches.py ...`. It never runs `git commit`:
`export` stages the clone's changes (`git add -A`, in the clone only) and diffs them against HEAD.
"""

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

APP = "apps/playground/"

# Which upstream-relative paths go into which patch. A path belongs to the first entry whose
# prefix matches. A changed path that matches none is an error: nothing is dropped silently.
# 0002 holds the whole state machine file and 0003 the whole route file, so that every patch
# is a self-consistent step (each compiles on top of the one before). 0003 also holds the few
# lines in LanguageClientSync.tsx that hand the Locate request to src/aac/.
# 0004 holds the Vite plugin that records the bundled modules for THIRD-PARTY-NOTICES.txt.
# Demo mode (a Vite build mode, see src/aac/mode.ts) lives in the same patches: its data side
# (mode.ts, the static workspace loader, no saving) in 0002, its UI side (header, route loader,
# hash history in router.tsx) in 0003. mode.ts is listed before the `src/aac/` prefix of 0003
# so that 0002 claims it.
PATCH_PATHS: list[tuple[str, list[str]]] = [
    (
        "0001-remove-cloud-features.patch",
        [
            f"{APP}index.html",
            f"{APP}src/monaco/config.ts",
            f"{APP}src/hooks/usePlayground.ts",
            f"{APP}src/routes/share.$shareId/",
            f"{APP}src/routes/redirect-after-auth.tsx",
        ],
    ),
    (
        "0002-server-workspace.patch",
        [
            f"{APP}src/state/playground-machine.ts",
            f"{APP}src/aac/server.ts",
            f"{APP}src/aac/saving.ts",
            f"{APP}src/aac/mode.ts",
        ],
    ),
    (
        "0003-editor-ui.patch",
        [
            f"{APP}src/router.tsx",
            f"{APP}src/routes/index.tsx",
            f"{APP}src/routes/w.$workspaceId/route.tsx",
            f"{APP}src/monaco/LanguageClientSync.tsx",
            f"{APP}src/aac/",
        ],
    ),
    (
        "0004-third-party-notices.patch",
        [
            f"{APP}vite.config.ts",
        ],
    ),
]

DIFF_RE = re.compile(r"^diff --git a/(?P<a>\S+) b/(?P<b>\S+)$")
HUNK_RE = re.compile(r"^@@ -\d+(?:,(?P<old>\d+))? \+\d+(?:,(?P<new>\d+))? @@")


@dataclass
class PatchStat:
    name: str
    existing_files: int = 0  # upstream files modified or deleted
    deleted_files: int = 0  # of those, deleted outright
    added: int = 0  # lines added in existing files
    removed: int = 0  # lines removed from existing files
    new_files: int = 0
    new_lines: int = 0
    files: list[str] = field(default_factory=list)

    @property
    def changed_lines(self) -> int:
        return self.added + self.removed


def parse_patch(name: str, text: str) -> PatchStat:
    """Count files and lines of one unified diff (git format).

    Lines are told apart by the hunk header counts, so a content line that happens to start
    with `---` or `+++` cannot be mistaken for a file header.
    """
    stat = PatchStat(name)
    kind = "modified"
    old_left = new_left = 0
    for line in text.splitlines():
        if old_left > 0 or new_left > 0:  # inside a hunk
            tag = line[:1]
            if tag == "+":
                new_left -= 1
                if kind == "new":
                    stat.new_lines += 1
                else:
                    stat.added += 1
            elif tag == "-":
                old_left -= 1
                stat.removed += 1
            elif tag == " ":
                old_left -= 1
                new_left -= 1
            continue
        header = DIFF_RE.match(line)
        if header:
            kind = "modified"
            stat.files.append(header.group("b"))
            stat.existing_files += 1
        elif line.startswith("new file mode"):
            kind = "new"
            stat.new_files += 1
            stat.existing_files -= 1
        elif line.startswith("deleted file mode"):
            kind = "deleted"
            stat.deleted_files += 1
        elif hunk := HUNK_RE.match(line):
            old_left = int(hunk.group("old") or 1)
            new_left = int(hunk.group("new") or 1)
    return stat


def stat_patch(path: Path) -> PatchStat:
    return parse_patch(path.name, path.read_bytes().decode("utf-8", errors="replace"))


def stat_dir(patch_dir: Path) -> list[PatchStat]:
    if not patch_dir.is_dir():
        return []
    return [stat_patch(p) for p in sorted(patch_dir.glob("*.patch"))]


def total(stats: Sequence[PatchStat]) -> PatchStat:
    out = PatchStat("TOTAL")
    for s in stats:
        out.existing_files += s.existing_files
        out.deleted_files += s.deleted_files
        out.added += s.added
        out.removed += s.removed
        out.new_files += s.new_files
        out.new_lines += s.new_lines
        out.files.extend(s.files)
    return out


def format_stats(stats: Sequence[PatchStat]) -> str:
    rows = [*stats, total(stats)]
    head = (
        f"{'patch':<36} {'existing files':>14} {'(deleted)':>9} {'+lines':>7} {'-lines':>7}"
        f" {'new files':>10} {'new lines':>10}"
    )
    lines = [head, "-" * len(head)]
    for s in rows:
        if s.name == "TOTAL":
            lines.append("-" * len(head))
        lines.append(
            f"{s.name:<36} {s.existing_files:>14} {s.deleted_files:>9} {s.added:>7} {s.removed:>7}"
            f" {s.new_files:>10} {s.new_lines:>10}"
        )
    grand = rows[-1]
    lines.append(
        f"changed lines in existing upstream files (added + removed): {grand.changed_lines}"
    )
    return "\n".join(lines)


def _git(clone: Path, *args: str, check: bool = True) -> bytes:
    proc = subprocess.run(["git", "-C", str(clone), *args], capture_output=True, check=False)
    if check and proc.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {proc.stderr.decode(errors='replace')}")
    return proc.stdout


def assign(paths: Sequence[str]) -> dict[str, list[str]]:
    """Group changed paths by patch name; raise on a path no patch claims."""
    groups: dict[str, list[str]] = {name: [] for name, _ in PATCH_PATHS}
    for path in paths:
        for name, prefixes in PATCH_PATHS:
            if any(path == p or (p.endswith("/") and path.startswith(p)) for p in prefixes):
                groups[name].append(path)
                break
        else:
            raise SystemExit(f"changed path {path} belongs to no patch: add it to PATCH_PATHS")
    return groups


def export(clone: Path, patch_dir: Path) -> list[Path]:
    """Rewrite the patch files from the clone's working tree changes against HEAD."""
    _git(clone, "add", "-A")  # stage only; this tool never commits
    names = _git(clone, "diff", "--cached", "--name-only", "-z", "HEAD").decode().split("\0")
    changed = sorted(n for n in names if n)
    groups = assign(changed)
    patch_dir.mkdir(parents=True, exist_ok=True)
    for old in patch_dir.glob("*.patch"):
        old.unlink()
    written = []
    for name, paths in groups.items():
        if not paths:
            continue
        diff = _git(
            clone,
            "diff",
            "--cached",
            "--binary",
            "--no-color",
            "--no-ext-diff",
            "HEAD",
            "--",
            *paths,
        )
        target = patch_dir / name
        target.write_bytes(diff.replace(b"\r\n", b"\n"))  # LF only, whatever the checkout used
        written.append(target)
    return written


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    stat_cmd = sub.add_parser("stat", help="size of the patch set")
    stat_cmd.add_argument("patch_dir", type=Path)
    export_cmd = sub.add_parser("export", help="regenerate the patches from a clone")
    export_cmd.add_argument("clone", type=Path)
    export_cmd.add_argument("patch_dir", type=Path)
    args = parser.parse_args(argv)

    if args.command == "stat":
        stats = stat_dir(args.patch_dir)
        if not stats:
            print(f"no patches in {args.patch_dir}")
        print(format_stats(stats))
        return 0
    for path in export(args.clone, args.patch_dir):
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
