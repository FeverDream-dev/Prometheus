from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def isolated_environment(tmp_path, monkeypatch):
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("PROMETHEUS_HOME", str(fake_home / ".prometheus"))
    monkeypatch.chdir(tmp_path)
    original_cwd = Path.cwd()
    yield tmp_path
    os.chdir(original_cwd)


class TestNoRepoCheckoutRequired:
    def test_load_registry_works_without_config_dir(self, isolated_environment, monkeypatch):
        from importlib import reload

        assert not (Path.cwd() / "config" / "bundles-v2").exists()
        assert not (Path.cwd() / "config" / "bundles").exists()

        import prometheus_cli.bundles
        reload(prometheus_cli.bundles)
        registry = prometheus_cli.bundles.load_registry()
        assert len(registry) >= 8
        ids = {b.id for b in registry}
        assert "spark-cpu-8gb" in ids

    def test_bundles_list_cli_without_repo(self, isolated_environment):
        from typer.testing import CliRunner
        from prometheus_cli.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["bundles", "list", "--json"])
        assert result.exit_code == 0
        import json
        data = json.loads(result.stdout)
        assert len(data) >= 8

    def test_setup_dry_run_without_repo(self, isolated_environment):
        from typer.testing import CliRunner
        from prometheus_cli.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert result.exit_code == 0
        assert "No bundles found" not in result.stdout

    def test_doctor_works_without_repo(self, isolated_environment):
        from typer.testing import CliRunner
        from prometheus_cli.cli import app

        runner = CliRunner()
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0


class TestResolveFromCleanHome:
    def test_resolve_bundles_dir_defaults_to_packaged(self, isolated_environment):
        from prometheus_cli.resources import resolve_bundles_dir, get_default_bundles_dir

        result = resolve_bundles_dir()
        assert result == get_default_bundles_dir()

    def test_resolve_bundles_v1_dir_defaults_to_packaged(self, isolated_environment):
        from prometheus_cli.resources import resolve_bundles_v1_dir, get_default_bundles_v1_dir

        result = resolve_bundles_v1_dir()
        assert result == get_default_bundles_v1_dir()

    def test_project_overrides_take_precedence(self, isolated_environment):
        from prometheus_cli.resources import resolve_bundles_dir

        project_bundles = Path.cwd() / ".prometheus" / "bundles"
        project_bundles.mkdir(parents=True)
        (project_bundles / "custom.yaml").write_text("id: custom\n", encoding="utf-8")

        result = resolve_bundles_dir()
        assert result == project_bundles

    def test_explicit_overrides_everything(self, isolated_environment, tmp_path):
        from prometheus_cli.resources import resolve_bundles_dir

        explicit_dir = tmp_path / "explicit_bundles"
        explicit_dir.mkdir()
        result = resolve_bundles_dir(explicit=explicit_dir)
        assert result == explicit_dir


class TestFindBundleWithoutRepo:
    def test_find_bundle_by_id_from_packaged(self, isolated_environment):
        from prometheus_cli.bundles import find_bundle

        bundle = find_bundle("spark-cpu-8gb")
        assert bundle is not None
        assert bundle.id == "spark-cpu-8gb"

    def test_find_unknown_returns_none(self, isolated_environment):
        from prometheus_cli.bundles import find_bundle

        assert find_bundle("nonexistent-bundle") is None
