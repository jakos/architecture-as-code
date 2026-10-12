import importlib.util
from pathlib import Path

import pytest

ENTRYPOINT = Path(__file__).resolve().parents[2] / "docker" / "editor" / "entrypoint.py"
spec = importlib.util.spec_from_file_location("editor_entrypoint", ENTRYPOINT)
entrypoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entrypoint)

MODEL_DIR = Path("/home/coder/model")


def test_editor_command_defaults_to_code_server():
    cmd = entrypoint.editor_command({"PASSWORD": "x"}, MODEL_DIR)
    assert cmd[0] == "code-server"
    assert cmd[-1] == str(MODEL_DIR)
    assert "password" in cmd


def test_editor_command_web_runs_web_editor():
    env = {
        "EDITOR_UI": "web",
        "MODEL_PATH": "examples/shop",
        "RENDER_URL": "http://127.0.0.1:8095",
    }
    cmd = entrypoint.editor_command(env, MODEL_DIR)
    assert cmd[:2] == ["python3", "/usr/local/lib/poc/web_editor.py"]
    assert cmd[cmd.index("--repo") + 1] == str(MODEL_DIR)
    assert cmd[cmd.index("--path") + 1] == "examples/shop"
    assert cmd[cmd.index("--render-url") + 1] == "http://127.0.0.1:8095"
    assert "code-server" not in cmd


def test_web_mode_needs_render_url():
    with pytest.raises(entrypoint.SetupError, match="RENDER_URL"):
        entrypoint.editor_command({"EDITOR_UI": "web", "MODEL_PATH": "m"}, MODEL_DIR)


def test_unknown_editor_ui_is_rejected():
    with pytest.raises(entrypoint.SetupError, match="EDITOR_UI"):
        entrypoint.editor_command({"EDITOR_UI": "vim"}, MODEL_DIR)


def test_likec4_renderer_uses_hmr_port_when_set():
    cmd, _ = entrypoint.renderer_command("likec4", MODEL_DIR, {"HMR_PORT": "24679"})
    assert cmd[cmd.index("--hmr-port") + 1] == "24679"
    without, _ = entrypoint.renderer_command("likec4", MODEL_DIR, {})
    assert "--hmr-port" not in without
    legacy, _ = entrypoint.renderer_command("likec4", MODEL_DIR)
    assert legacy == without


def test_renderer_env_has_no_password():
    _, extra = entrypoint.renderer_command("likec4", MODEL_DIR)
    env = entrypoint.renderer_env({"PASSWORD": "s3cret", "PATH": "/bin"}, extra)
    assert "PASSWORD" not in env
    assert env["PATH"] == "/bin"
    assert env["CHOKIDAR_USEPOLLING"] == "true"


def test_editor_command_playground_serves_static():
    env = {"EDITOR_UI": "playground", "MODEL_PATH": "examples/shop"}
    cmd = entrypoint.editor_command(env, MODEL_DIR)
    assert cmd[:2] == ["python3", "/usr/local/lib/poc/web_editor.py"]
    assert cmd[cmd.index("--repo") + 1] == str(MODEL_DIR)
    assert cmd[cmd.index("--path") + 1] == "examples/shop"
    assert cmd[cmd.index("--port") + 1] == "8080"
    assert cmd[cmd.index("--static") + 1] == "/usr/local/share/model-editor"
    assert "code-server" not in cmd


def test_playground_mode_starts_no_renderer():
    assert entrypoint.needs_renderer({"EDITOR_UI": "playground"}) is False
    assert entrypoint.needs_renderer({"EDITOR_UI": "web"}) is True
    assert entrypoint.needs_renderer({}) is True  # code-server is the default
    with pytest.raises(entrypoint.SetupError, match="EDITOR_UI"):
        entrypoint.needs_renderer({"EDITOR_UI": "vim"})


def test_playground_mode_needs_no_render_url():
    env = {"EDITOR_UI": "playground", "MODEL_PATH": "examples/shop"}
    cmd = entrypoint.editor_command(env, MODEL_DIR)  # no RENDER_URL, no error
    assert "--render-url" not in cmd
    with pytest.raises(entrypoint.SetupError, match="MODEL_PATH"):
        entrypoint.editor_command({"EDITOR_UI": "playground"}, MODEL_DIR)
