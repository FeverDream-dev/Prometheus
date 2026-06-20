from __future__ import annotations

from prometheus_cli import tui_commands
from prometheus_cli.bundles import classify_registry, load_registry
from prometheus_cli.hardware import HardwareReport
from prometheus_cli.models import Settings
from prometheus_cli.onboarding import OllamaStatus


def _hw(ram=8, vram=0, disk=200):
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        cpu_features=[], disk_free_gb=disk,
    )


def _ollama(running=True, models=None):
    return OllamaStatus(installed=True, running=running, models=models or [], install_hint="")


def test_help_lists_all_commands():
    lines = tui_commands.help_lines()
    joined = "\n".join(lines)
    for cmd in ("/settings", "/bundles", "/models", "/doctor", "/qualify", "/modes", "/clear", "/help"):
        assert cmd in joined


def test_doctor_lines_reports_hardware_and_ollama():
    lines = tui_commands.doctor_lines(_hw(ram=16, vram=8, disk=100), _ollama(models=["m1", "m2"]))
    joined = " ".join(lines)
    assert "16 GB" in joined
    assert "8 GB" in joined
    assert "running" in joined
    assert "2 models" in joined


def test_doctor_lines_shows_service_down():
    lines = tui_commands.doctor_lines(_hw(), _ollama(running=False))
    assert any("NOT running" in line for line in lines)


def test_models_lines_lists_installed():
    lines = tui_commands.models_lines(_ollama(models=["granite4.1:3b", "llama3.2:latest"]))
    assert any("granite4.1:3b" in line for line in lines)
    assert any("llama3.2:latest" in line for line in lines)


def test_modes_lines_three_modes():
    lines = tui_commands.modes_lines()
    joined = "\n".join(lines)
    for mode in ("copilot", "pilot", "astronaut"):
        assert mode in joined


def test_settings_lines_shows_packages_and_quota_label():
    classified = classify_registry(load_registry(), _hw(ram=8, vram=0, disk=200), ["granite4.1:3b"])
    settings = Settings(active_bundle_id="spark-cpu-8gb")
    lines = tui_commands.settings_lines(settings, classified, ["granite4.1:3b"])
    joined = "\n".join(lines)
    assert "Model Packages" in joined
    assert "active: spark-cpu-8gb" in joined
    assert "unlimited" in joined
    assert "Spark" in joined
    assert "[pulled]" in joined


def test_settings_lines_marks_metered_when_unlimited_false():
    classified = classify_registry(load_registry(), _hw(ram=8, vram=0, disk=200))
    settings = Settings(unlimited_local_sessions=False)
    lines = tui_commands.settings_lines(settings, classified)
    assert any("metered" in line for line in lines)


def test_settings_lines_tags_incompatible_and_experimental():
    classified = classify_registry(load_registry(), _hw(ram=8, vram=0, disk=200))
    settings = Settings()
    lines = tui_commands.settings_lines(settings, classified)
    joined = "\n".join(lines)
    assert "incompatible" in joined
    assert "experimental" in joined
    assert "add-on" in joined


def test_tools_lines_lists_categories():
    joined = "\n".join(tui_commands.tools_lines())
    for cat in ("Repository", "Process", "Git", "Browser", "Web", "MCP"):
        assert cat in joined


def test_mcp_lines_marks_output_untrusted():
    joined = "\n".join(tui_commands.mcp_lines())
    assert "untrusted" in joined


def test_providers_lines_local_only_disables_cloud():
    lines = tui_commands.providers_lines(Settings(local_only=True))
    joined = "\n".join(lines)
    assert "ollama" in joined
    assert "disabled" in joined


def test_permissions_lines_shows_limits_and_unlimited():
    lines = tui_commands.permissions_lines(Settings())
    joined = "\n".join(lines)
    assert "Autonomy mode" in joined
    assert "unlimited" in joined
    assert "Sandbox" in joined


def test_sessions_lines_handles_empty(tmp_path, monkeypatch):
    import prometheus_cli.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_HOME", tmp_path)
    monkeypatch.setattr("prometheus_cli.config.ensure_home", lambda: tmp_path)
    lines = tui_commands.sessions_lines()
    assert len(lines) >= 1


def test_help_lists_new_slash_commands():
    lines = tui_commands.help_lines()
    joined = "\n".join(lines)
    for cmd in ("/resume", "/mode", "/exit"):
        assert cmd in joined


def test_settings_lines_shows_all_editable_fields():
    classified = classify_registry(load_registry(), _hw(ram=16, vram=8, disk=200), [])
    lines = tui_commands.settings_lines(Settings(), classified)
    joined = "\n".join(lines)
    for field in ("autonomy mode", "sandbox", "telemetry", "max steps", "max runtime",
                  "multi-agent review", "audio markers", "local sessions"):
        assert field in joined, f"missing {field}"


def test_mode_switch_persists_valid_mode(tmp_path, monkeypatch):
    monkeypatch.setattr("prometheus_cli.config.CONFIG_HOME", tmp_path)
    (tmp_path / "bundles").mkdir()
    settings = Settings()
    lines = tui_commands.mode_switch_lines(settings, "astronaut")
    assert settings.mode.value == "astronaut"
    assert "astronaut" in "".join(lines)


def test_mode_switch_rejects_invalid_mode():
    settings = Settings()
    lines = tui_commands.mode_switch_lines(settings, "supervisor")
    assert settings.mode.value == "pilot"
    assert "Unknown mode" in "".join(lines)


def test_resume_lines_without_id_errors():
    lines = tui_commands.resume_lines("")
    assert "needs a session id" in "".join(lines)
