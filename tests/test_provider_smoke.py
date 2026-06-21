"""Provider smoke probe CLI tests."""
from __future__ import annotations

from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


def test_provider_list_shows_all_presets():
    res = runner.invoke(app, ["provider", "list"])
    assert res.exit_code == 0
    assert "ollama" in res.output
    assert "openai" in res.output
    assert "mistral" in res.output


def test_provider_list_json():
    res = runner.invoke(app, ["provider", "list", "--json"])
    assert res.exit_code == 0
    import json

    data = json.loads(res.stdout)
    ids = [p["id"] for p in data]
    assert "ollama" in ids
    assert len(ids) >= 8


def test_provider_smoke_fails_gracefully_on_dead_endpoint():
    res = runner.invoke(
        app,
        ["provider", "smoke", "--provider", "ollama", "--model", "fake",
         "--base-url", "http://127.0.0.1:1", "--timeout", "2"],
    )
    assert res.exit_code == 1


def test_provider_list_includes_local_and_cloud():
    res = runner.invoke(app, ["provider", "list"])
    assert res.exit_code == 0
    assert "local" in res.output.lower()
    assert "cloud" in res.output.lower()
