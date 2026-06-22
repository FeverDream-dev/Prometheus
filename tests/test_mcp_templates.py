from __future__ import annotations


import pytest
from typer.testing import CliRunner

from prometheus_cli.cli import app
from prometheus_cli.mcp_templates import (
    list_templates,
    load_template,
    install_template,
)


@pytest.fixture
def runner():
    return CliRunner()


class TestTemplatesList:
    def test_list_includes_whatsapp_starter(self):
        templates = list_templates()
        assert "whatsapp-starter" in templates

    def test_list_returns_sorted(self):
        templates = list_templates()
        assert templates == sorted(templates)


class TestTemplateLoad:
    def test_load_whatsapp_starter(self):
        t = load_template("whatsapp-starter")
        assert t.id == "whatsapp-starter"
        assert t.name
        assert t.description
        assert len(t.servers) >= 1
        assert len(t.setup_steps) >= 1

    def test_load_has_warning(self):
        t = load_template("whatsapp-starter")
        assert t.warning
        assert "STARTER TEMPLATE" in t.warning or "starter" in t.warning.lower()

    def test_load_nonexistent_raises(self):
        with pytest.raises(FileNotFoundError):
            load_template("nonexistent-template")

    def test_server_has_trust_level(self):
        t = load_template("whatsapp-starter")
        for s in t.servers:
            assert s.trust_level in ("untrusted", "trusted")

    def test_server_has_network_scope(self):
        t = load_template("whatsapp-starter")
        for s in t.servers:
            assert s.network_scope in ("none", "outbound")


class TestTemplateInstall:
    def test_install_creates_mcp_json(self, tmp_path):
        mcp_path = tmp_path / "mcp.json"
        result = install_template("whatsapp-starter", mcp_path)
        assert result.is_file()
        import json
        data = json.loads(result.read_text(encoding="utf-8"))
        assert "servers" in data
        names = [s["name"] for s in data["servers"]]
        assert "whatsapp-bridge" in names

    def test_install_does_not_duplicate(self, tmp_path):
        mcp_path = tmp_path / "mcp.json"
        install_template("whatsapp-starter", mcp_path)
        install_template("whatsapp-starter", mcp_path)
        import json
        data = json.loads(mcp_path.read_text(encoding="utf-8"))
        names = [s["name"] for s in data["servers"]]
        assert names.count("whatsapp-bridge") == 1


class TestMcpTemplatesCli:
    def test_mcp_templates_command(self, runner):
        result = runner.invoke(app, ["mcp", "templates"])
        assert result.exit_code == 0
        assert "whatsapp-starter" in result.stdout

    def test_mcp_template_inspect(self, runner):
        result = runner.invoke(app, ["mcp", "template", "inspect", "whatsapp-starter"])
        assert result.exit_code == 0
        assert "WhatsApp" in result.stdout
        assert "WARNING" in result.stdout or "WARNING" in result.stdout.upper()

    def test_mcp_template_install(self, runner, tmp_path, monkeypatch):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", home)
        result = runner.invoke(app, ["mcp", "template", "install", "whatsapp-starter"])
        assert result.exit_code == 0
        assert "Installed" in result.stdout

    def test_mcp_template_inspect_nonexistent(self, runner):
        result = runner.invoke(app, ["mcp", "template", "inspect", "nonexistent"])
        assert result.exit_code == 1


class TestMcpSecurityBoundary:
    def test_server_trust_level_is_untrusted(self):
        t = load_template("whatsapp-starter")
        for s in t.servers:
            assert s.trust_level == "untrusted"

    def test_template_warning_mentions_setup_required(self):
        t = load_template("whatsapp-starter")
        assert t.warning
        warning_lower = t.warning.lower()
        assert "configure" in warning_lower or "install" in warning_lower or "run" in warning_lower
