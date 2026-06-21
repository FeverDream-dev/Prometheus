"""Assets CLI command tests."""
from __future__ import annotations

from typer.testing import CliRunner

from prometheus_cli.cli import app

runner = CliRunner()


def test_assets_help():
    res = runner.invoke(app, ["assets", "--help"])
    assert res.exit_code == 0
    for cmd in ("doctor", "setup", "models", "generate", "manifest"):
        assert cmd in res.output


def test_assets_doctor_runs():
    res = runner.invoke(app, ["assets", "doctor"])
    assert res.exit_code == 0
    assert "AssetForge" in res.output or "torch" in res.output


def test_assets_setup_runs():
    res = runner.invoke(app, ["assets", "setup"])
    assert res.exit_code == 0


def test_assets_models_lists_known():
    res = runner.invoke(app, ["assets", "models"])
    assert res.exit_code == 0
    assert "license" in res.output.lower()


def test_assets_manifest_missing(tmp_path):
    empty_dir = tmp_path / "no-manifest"
    empty_dir.mkdir()
    res = runner.invoke(app, ["assets", "manifest", str(empty_dir)])
    assert res.exit_code == 1
