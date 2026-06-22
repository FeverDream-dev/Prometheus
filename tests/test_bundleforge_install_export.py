from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from prometheus_cli.cli import app


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    fake_prometheus = fake_home / ".prometheus"
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("PROMETHEUS_HOME", str(fake_prometheus))
    monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", fake_prometheus)
    monkeypatch.chdir(tmp_path)


class TestBundleforgeCreate:
    def test_create_from_template(self, runner, tmp_path):
        out = tmp_path / "out"
        result = runner.invoke(app, ["bundleforge", "create", "game-dev-lite", "--out", str(out)])
        assert result.exit_code == 0, result.stdout
        bundle_path = out / "game-dev-lite" / "bundle.yaml"
        assert bundle_path.is_file()

    def test_create_unknown_template_fails(self, runner, tmp_path):
        result = runner.invoke(app, ["bundleforge", "create", "nonexistent", "--out", str(tmp_path / "out")])
        assert result.exit_code == 1

    def test_create_no_overwrite_without_force(self, runner, tmp_path):
        out = tmp_path / "out"
        runner.invoke(app, ["bundleforge", "create", "cpu-only-emergency", "--out", str(out)])
        result = runner.invoke(app, ["bundleforge", "create", "cpu-only-emergency", "--out", str(out)])
        assert result.exit_code == 1

    def test_create_with_force_overwrites(self, runner, tmp_path):
        out = tmp_path / "out"
        runner.invoke(app, ["bundleforge", "create", "cpu-only-emergency", "--out", str(out)])
        result = runner.invoke(app, ["bundleforge", "create", "cpu-only-emergency", "--out", str(out), "--force"])
        assert result.exit_code == 0


class TestBundleforgeInstall:
    def test_install_from_template(self, runner):
        result = runner.invoke(app, ["bundleforge", "install", "game-dev-lite"])
        assert result.exit_code == 0, result.stdout
        assert "Installed" in result.stdout

    def test_install_no_overwrite_without_force(self, runner):
        runner.invoke(app, ["bundleforge", "install", "cpu-only-emergency"])
        result = runner.invoke(app, ["bundleforge", "install", "cpu-only-emergency"])
        assert result.exit_code == 1

    def test_install_with_force(self, runner):
        runner.invoke(app, ["bundleforge", "install", "cpu-only-emergency"])
        result = runner.invoke(app, ["bundleforge", "install", "cpu-only-emergency", "--force"])
        assert result.exit_code == 0

    def test_installed_bundle_appears_in_v2_registry(self, runner):
        result = runner.invoke(app, ["bundleforge", "install", "rag-docs-local"])
        assert result.exit_code == 0, result.stdout
        assert "Installed" in result.stdout
        from prometheus_cli.config import CONFIG_HOME
        v2_file = CONFIG_HOME / "bundles" / "rag-docs-local.yaml"
        assert v2_file.is_file(), f"expected {v2_file} to exist"
        data = yaml.safe_load(v2_file.read_text(encoding="utf-8"))
        assert data["schema_version"] == 2
        assert data["id"] == "rag-docs-local"


class TestBundleforgeExport:
    def test_export_template(self, runner, tmp_path):
        out = tmp_path / "exported"
        result = runner.invoke(app, ["bundleforge", "export", "game-dev-lite", "--out", str(out)])
        assert result.exit_code == 0, result.stdout
        bundle_dir = out / "game-dev-lite"
        assert (bundle_dir / "bundle.yaml").is_file()
        assert (bundle_dir / "README.md").is_file()
        assert (bundle_dir / "LICENSE_NOTES.md").is_file()


class TestBundleforgeInspect:
    def test_inspect_template(self, runner):
        result = runner.invoke(app, ["bundleforge", "inspect", "game-dev-lite"])
        assert result.exit_code == 0
        assert "Game Dev" in result.stdout

    def test_inspect_file(self, runner, tmp_path):
        out = tmp_path / "out"
        runner.invoke(app, ["bundleforge", "create", "cpu-only-emergency", "--out", str(out)])
        bundle_file = out / "cpu-only-emergency" / "bundle.yaml"
        result = runner.invoke(app, ["bundleforge", "inspect", str(bundle_file)])
        assert result.exit_code == 0
        assert "cpu-only-emergency" in result.stdout


class TestBundleforgeValidate:
    def test_validate_template_passes(self, runner):
        result = runner.invoke(app, ["bundleforge", "validate", "game-dev-lite"])
        assert result.exit_code == 0
        assert "VALID" in result.stdout

    def test_validate_json_output(self, runner):
        result = runner.invoke(app, ["bundleforge", "validate", "cpu-only-emergency", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)
        assert data["valid"] is True


class TestBundleforgeRecommend:
    def test_recommend_game(self, runner):
        result = runner.invoke(app, ["bundleforge", "recommend", "I want to build a 2D game with sprites"])
        assert result.exit_code == 0
        assert "game" in result.stdout.lower()

    def test_recommend_json(self, runner):
        result = runner.invoke(app, ["bundleforge", "recommend", "I want RAG for my documents", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)
        assert data["use_case"] == "rag_documents"


class TestBundleforgeSearch:
    def test_search_returns_results(self, runner):
        result = runner.invoke(app, ["bundleforge", "search", "game"])
        assert result.exit_code == 0
        assert "game" in result.stdout.lower()

    def test_search_json(self, runner):
        result = runner.invoke(app, ["bundleforge", "search", "rag", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)
        assert len(data) >= 1
