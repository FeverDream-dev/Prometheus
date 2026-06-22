from __future__ import annotations


import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app


@pytest.fixture
def runner():
    return CliRunner()


class TestSetupDryRunFindsBundles:
    def test_setup_dry_run_exits_zero(self, runner):
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert result.exit_code == 0, result.stdout

    def test_setup_dry_run_shows_available_bundles(self, runner):
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert "Available bundles" in result.stdout
        assert result.exit_code == 0

    def test_setup_dry_run_does_not_say_no_bundles_found(self, runner):
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert "No bundles found" not in result.stdout

    def test_setup_dry_run_shows_recommendation(self, runner):
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert "Dry run complete" in result.stdout

    def test_setup_dry_run_does_not_write_config(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / "should_not_exist"))
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert result.exit_code == 0
        assert "No files written" in result.stdout
        config_file = tmp_path / "should_not_exist" / "config.yaml"
        assert not config_file.exists()


class TestSetupDryRunFromCleanHome:
    def test_setup_dry_run_works_with_empty_home(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / "clean_home"))
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert result.exit_code == 0
        assert "Available bundles" in result.stdout

    def test_setup_dry_run_does_not_require_explicit_bundles_dir(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("PROMETHEUS_HOME", str(tmp_path / "clean_home"))
        monkeypatch.chdir(tmp_path)
        result = runner.invoke(app, ["setup", "--dry-run"])
        assert result.exit_code == 0


class TestBundlesListFromPackagedDefaults:
    def test_bundles_list_exits_zero(self, runner):
        result = runner.invoke(app, ["bundles", "list"])
        assert result.exit_code == 0, result.stdout

    def test_bundles_list_json_has_known_ids(self, runner):
        import json
        result = runner.invoke(app, ["bundles", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        ids = {b["id"] for b in data}
        assert "spark-cpu-8gb" in ids
        assert "ember-8gb-gpu" in ids

    def test_bundles_inspect_works(self, runner):
        result = runner.invoke(app, ["bundles", "inspect", "spark-cpu-8gb"])
        assert result.exit_code == 0
        assert "spark-cpu-8gb" in result.stdout
