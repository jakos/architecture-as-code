import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import validate_models
from validate_models import IMAGE, REPO, find_projects, validate_commands


def test_finds_example_project():
    assert REPO / "examples" / "shop" in find_projects(REPO, ("examples",))


def test_skips_likec4_and_build_dirs(tmp_path):
    (tmp_path / "real").mkdir()
    (tmp_path / "real" / "likec4.config.json").write_text("{}")
    for skipped in (".likec4", "node_modules", "build"):
        (tmp_path / skipped / "copy").mkdir(parents=True)
        (tmp_path / skipped / "copy" / "likec4.config.json").write_text("{}")
    assert find_projects(REPO, (str(tmp_path),)) == [tmp_path / "real"]


def test_commands_validate_and_format_check():
    project = REPO / "examples" / "shop"
    validate, fmt = validate_commands("podman", project)
    assert validate[-1] == "validate"
    assert fmt[-2:] == ["format", "--check"]
    for cmd in (validate, fmt):
        assert f"{project}:/data:ro" in cmd
        assert IMAGE in cmd
    assert IMAGE.endswith(":1.59.4")


def test_no_project_exits_1(tmp_path, capsys):
    assert validate_models.main([str(tmp_path)]) == 1
    assert "no likec4 project found" in capsys.readouterr().err
