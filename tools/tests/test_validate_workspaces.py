import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from validate_workspaces import REPO, find_workspaces, validate_command


def test_finds_example_workspace():
    found = find_workspaces(REPO, ("examples",))
    assert REPO / "examples" / "shop" / "workspace.dsl" in found


def test_command_mounts_repo_and_uses_posix_path():
    ws = REPO / "examples" / "shop" / "workspace.dsl"
    cmd = validate_command("podman", REPO, ws)
    assert cmd[-2:] == ["-w", "/repo/examples/shop/workspace.dsl"]
