from __future__ import annotations

from unittest import mock

import httpx
from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


def test_sandbox_doctor_runs():
    result = runner.invoke(app, ["sandbox", "doctor"])
    assert result.exit_code == 0
    assert "basic" in result.stdout
    assert "docker" in result.stdout
    assert "native" in result.stdout


def test_sandbox_test_runs_on_tmp_workspace(tmp_path):
    result = runner.invoke(app, ["sandbox", "test", "--workspace", str(tmp_path)])
    assert result.exit_code == 0, result.stdout
    assert "passed=" in result.stdout
    assert (tmp_path / ".prometheus" / "sandbox-test-report.json").exists()


def test_sandbox_test_json_output(tmp_path):
    import json

    result = runner.invoke(app, ["sandbox", "test", "--workspace", str(tmp_path), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "results" in data and "summary" in data


def test_sandbox_test_exits_nonzero_only_on_required_failure(tmp_path):
    result = runner.invoke(app, ["sandbox", "test", "--workspace", str(tmp_path)])
    assert result.exit_code == 0


def test_provider_smoke_ollama_health_and_completion(tmp_path):
    tags = httpx.Response(200, json={"models": [{"name": "granite4.1:3b"}]},
                          request=httpx.Request("GET", "http://x/api/tags"))
    gen = httpx.Response(200, json={"response": "PROMETHEUS_SANDBOX_READY"},
                         request=httpx.Request("POST", "http://x/api/generate"))
    unload = httpx.Response(200, request=httpx.Request("POST", "http://x/api/generate"))
    with mock.patch("httpx.Client") as client_cls:
        c = client_cls.return_value
        c.get.return_value = tags
        c.post.side_effect = [gen, unload]
        c.close.return_value = None
        result = runner.invoke(app, ["provider", "smoke", "--provider", "ollama",
                                     "--model", "granite4.1:3b"])
    assert result.exit_code == 0, result.stdout
    assert "completion: OK" in result.stdout


def test_provider_smoke_fails_on_unreachable(tmp_path):
    with mock.patch("httpx.Client") as client_cls:
        client_cls.return_value.get.side_effect = httpx.ConnectError("no")
        client_cls.return_value.post.side_effect = httpx.ConnectError("no")
        result = runner.invoke(app, ["provider", "smoke", "--provider", "ollama",
                                     "--model", "granite4.1:3b"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout


def test_models_inspect_resolves_alias():
    result = runner.invoke(app, ["models", "inspect", "vibethinker-q2"])
    assert result.exit_code == 0
    assert "hf.co/prithivMLmods/VibeThinker-3B-GGUF:Q2_K" in result.stdout
    assert "alias" in result.stdout.lower()


def test_models_inspect_unknown_tag_passthrough():
    result = runner.invoke(app, ["models", "inspect", "some-model:tag"])
    assert result.exit_code == 0
    assert "some-model:tag" in result.stdout
