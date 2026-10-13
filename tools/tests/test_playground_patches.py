import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import playground_patches

MODIFY = """\
diff --git a/apps/playground/src/a.ts b/apps/playground/src/a.ts
index 1111111..2222222 100644
--- a/apps/playground/src/a.ts
+++ b/apps/playground/src/a.ts
@@ -1,4 +1,4 @@
 keep
-old one
+new one
+new two
 keep
@@ -10,2 +11,1 @@
-gone
 keep
"""

NEW = """\
diff --git a/apps/playground/src/aac/b.ts b/apps/playground/src/aac/b.ts
new file mode 100644
index 0000000..3333333
--- /dev/null
+++ b/apps/playground/src/aac/b.ts
@@ -0,0 +1,3 @@
+one
+--- looks like a header but is content
+three
"""

DELETE = """\
diff --git a/apps/playground/src/old.ts b/apps/playground/src/old.ts
deleted file mode 100644
index 4444444..0000000
--- a/apps/playground/src/old.ts
+++ /dev/null
@@ -1,2 +0,0 @@
-x
-y
"""


def write(tmp_path, name, text):
    (tmp_path / name).write_bytes(text.encode())


def test_stat_counts_new_and_modified_files_separately(tmp_path):
    write(tmp_path, "0001-a.patch", MODIFY + NEW + DELETE)
    (stat,) = playground_patches.stat_dir(tmp_path)
    assert stat.existing_files == 2  # the modified file and the deleted one
    assert stat.deleted_files == 1
    assert stat.new_files == 1
    assert stat.new_lines == 3
    assert stat.files == [
        "apps/playground/src/a.ts",
        "apps/playground/src/aac/b.ts",
        "apps/playground/src/old.ts",
    ]


def test_stat_counts_added_and_removed_lines(tmp_path):
    write(tmp_path, "0001-a.patch", MODIFY + NEW)
    write(tmp_path, "0002-b.patch", DELETE)
    stats = playground_patches.stat_dir(tmp_path)
    assert [(s.added, s.removed) for s in stats] == [(2, 2), (0, 2)]  # new-file lines not counted
    grand = playground_patches.total(stats)
    assert (grand.added, grand.removed, grand.changed_lines) == (2, 4, 6)
    assert grand.existing_files == 2 and grand.new_files == 1
    text = playground_patches.format_stats(stats)
    assert "0001-a.patch" in text and "TOTAL" in text
    assert "(added + removed): 6" in text


def test_stat_handles_empty_dir(tmp_path, capsys):
    assert playground_patches.stat_dir(tmp_path) == []
    assert playground_patches.stat_dir(tmp_path / "missing") == []
    grand = playground_patches.total([])
    assert (grand.existing_files, grand.changed_lines, grand.new_files) == (0, 0, 0)
    assert playground_patches.main(["stat", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "no patches" in out and "TOTAL" in out


def test_assign_routes_paths_and_rejects_unknown_ones():
    app = playground_patches.APP
    groups = playground_patches.assign(
        [f"{app}index.html", f"{app}src/aac/x.tsx", f"{app}src/state/playground-machine.ts"]
    )
    assert groups["0001-remove-cloud-features.patch"] == [f"{app}index.html"]
    assert groups["0002-server-workspace.patch"] == [f"{app}src/state/playground-machine.ts"]
    assert groups["0003-editor-ui.patch"] == [f"{app}src/aac/x.tsx"]
    with pytest.raises(SystemExit, match="belongs to no patch"):
        playground_patches.assign([f"{app}package.json"])


def test_assign_sends_language_client_sync_to_0003_and_only_that_monaco_file():
    app = playground_patches.APP
    groups = playground_patches.assign([f"{app}src/monaco/LanguageClientSync.tsx"])
    assert groups["0003-editor-ui.patch"] == [f"{app}src/monaco/LanguageClientSync.tsx"]
    with pytest.raises(SystemExit, match="belongs to no patch"):
        playground_patches.assign([f"{app}src/monaco/MonacoEditor.tsx"])


def test_assign_sends_demo_mode_files_to_the_patch_that_owns_their_side():
    app = playground_patches.APP
    groups = playground_patches.assign([f"{app}src/aac/mode.ts", f"{app}src/router.tsx"])
    assert groups["0002-server-workspace.patch"] == [f"{app}src/aac/mode.ts"]
    assert groups["0003-editor-ui.patch"] == [f"{app}src/router.tsx"]
