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


def test_help_lists_setup_and_sandbox():
    joined = "\n".join(tui_commands.help_lines())
    for cmd in ("/setup", "/sandbox", "/vision", "/assets", "/astronaut"):
        assert cmd in joined


def test_sandbox_lines_reports_tiers():
    lines = tui_commands.sandbox_lines()
    joined = "\n".join(lines)
    assert "Sandbox" in joined
    for tier in ("off", "basic", "docker", "native"):
        assert tier in joined


def test_vision_lines_reports_playwright():
    lines = tui_commands.vision_lines()
    joined = "\n".join(lines)
    assert "Playwright" in joined
    assert "Vision" in joined


def test_assets_lines_reports_dependencies():
    lines = tui_commands.assets_lines()
    joined = "\n".join(lines)
    assert "AssetForge" in joined
    assert "torch" in joined
    assert "image tests" in joined


def test_astronaut_lines_shows_status(tmp_path):
    lines = tui_commands.astronaut_lines(tmp_path)
    joined = "\n".join(lines)
    assert "Astronaut" in joined
    assert "status" in joined
    assert "macro attempts" in joined


def test_setup_lines_shows_recommended_and_use_hints():
    classified = classify_registry(load_registry(), _hw(ram=8, vram=0, disk=200))
    settings = Settings()
    lines = tui_commands.setup_lines(settings, classified)
    joined = "\n".join(lines)
    assert "first-run setup" in joined
    assert "/use" in joined
    assert "spark-cpu-8gb" in joined


def test_setup_lines_shows_active_when_configured():
    classified = classify_registry(load_registry(), _hw(ram=8, vram=0, disk=200))
    settings = Settings(active_bundle_id="spark-cpu-8gb")
    lines = tui_commands.setup_lines(settings, classified)
    assert any("Active bundle: spark-cpu-8gb" in line for line in lines)


def test_first_run_banner_shows_when_no_bundle():
    lines = tui_commands.first_run_banner(Settings())
    assert len(lines) > 0
    joined = "\n".join(lines)
    assert "Welcome" in joined
    assert "/setup" in joined


def test_first_run_banner_empty_when_bundle_set():
    lines = tui_commands.first_run_banner(Settings(active_bundle_id="spark-cpu-8gb"))
    assert lines == []


def test_every_slash_command_has_tui_dispatch_handler():
    import inspect

    from prometheus_cli.tui import PrometheusApp

    source = inspect.getsource(PrometheusApp._handle_slash)
    missing = [cmd for cmd in tui_commands.SLASH_COMMANDS if cmd not in source]
    assert not missing, f"Commands registered in SLASH_COMMANDS but not dispatched in _handle_slash: {missing}"
