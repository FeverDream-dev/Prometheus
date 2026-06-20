from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import httpx
import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app
from prometheus_cli.onboarding import OllamaStatus, unload_model

runner = CliRunner()
ECHO_SERVER = Path(__file__).parent / "fixtures" / "mcp" / "echo_server.py"


def _ollama_running(models=None):
    return OllamaStatus(installed=True, running=True, models=models or [], install_hint="")


def _ollama_down():
    return OllamaStatus(installed=True, running=False, models=[], install_hint="")


def test_unload_model_single_returns_true_on_200():
    resp = httpx.Response(200, request=httpx.Request("POST", "http://x/api/generate"))
    with mock.patch("httpx.Client") as client_cls:
        client_cls.return_value.post.return_value = resp
        assert unload_model("llama3.2:latest") is True


def test_unload_model_returns_false_on_http_error():
    with mock.patch("httpx.Client") as client_cls:
        client_cls.return_value.post.side_effect = httpx.ConnectError("no")
        assert unload_model("llama3.2:latest") is False


def test_unload_all_models_evicts_each_resident():
    responses = [httpx.Response(200, request=httpx.Request("POST", "http://x")) for _ in range(2)]
    with mock.patch("httpx.Client") as client_cls, \
         mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama_running(["a", "b"])):
        client_cls.return_value.post.side_effect = responses
        assert unload_model(None) is True
        assert client_cls.return_value.post.call_count == 2


def test_models_list_shows_installed_models():
    with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama_running(["llama3.2:latest", "qwen:7b"])):
        result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 0
    assert "llama3.2:latest" in result.stdout
    assert "qwen:7b" in result.stdout


def test_models_list_errors_when_ollama_down():
    with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama_down()):
        result = runner.invoke(app, ["models", "list"])
    assert result.exit_code == 1
    assert "not responding" in result.stdout.lower()


def test_models_list_json_output():
    with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama_running(["llama3.2:latest"])):
        result = runner.invoke(app, ["models", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["models"] == ["llama3.2:latest"]


def test_models_unload_cli_evicts_model():
    with mock.patch("prometheus_cli.onboarding.check_ollama", return_value=_ollama_running(["llama3.2:latest"])), \
         mock.patch("prometheus_cli.onboarding.unload_model", return_value=True) as called:
        result = runner.invoke(app, ["models", "unload", "llama3.2:latest"])
    assert result.exit_code == 0
    called.assert_called_once()


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / "promhome"
    home.mkdir()
    monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", home)
    (home / "bundles").mkdir()
    (home / "sessions").mkdir()
    return home


def test_mcp_add_then_list_then_remove(isolated_home):
    add = runner.invoke(app, ["mcp", "add", "echo", "--", sys.executable, str(ECHO_SERVER)])
    assert add.exit_code == 0, add.stdout
    cfg = json.loads((isolated_home / "mcp.json").read_text())
    assert cfg["servers"][0]["name"] == "echo"
    assert cfg["servers"][0]["command"][0] == sys.executable

    listing = runner.invoke(app, ["mcp", "list"])
    assert listing.exit_code == 0
    assert "echo" in listing.stdout

    removed = runner.invoke(app, ["mcp", "remove", "echo"])
    assert removed.exit_code == 0
    cfg_after = json.loads((isolated_home / "mcp.json").read_text())
    assert cfg_after["servers"] == []


def test_mcp_add_rejects_bad_name(isolated_home):
    result = runner.invoke(app, ["mcp", "add", "../escape", "--", "python"])
    assert result.exit_code == 1


def test_mcp_list_empty(isolated_home):
    result = runner.invoke(app, ["mcp", "list"])
    assert result.exit_code == 0
    assert "No MCP servers" in result.stdout


def test_mcp_test_probes_real_echo_server(isolated_home):
    runner.invoke(app, ["mcp", "add", "echo", "--", sys.executable, str(ECHO_SERVER)])
    result = runner.invoke(app, ["mcp", "test", "echo"])
    assert result.exit_code == 0, result.stdout
    assert "Initialized" in result.stdout
    assert "echo" in result.stdout
    assert "fetch_doc" in result.stdout


def test_mcp_test_unknown_server_errors(isolated_home):
    result = runner.invoke(app, ["mcp", "test", "nope"])
    assert result.exit_code == 1
