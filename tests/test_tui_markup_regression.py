"""Regression tests pinning the fix for the literal-markup leak in the TUI.

The bug: ``tui.py`` used Textual's ``Log`` widget, which writes strings verbatim
and does NOT parse Rich markup, so ``[bold yellow]Welcome...[/bold yellow]``
appeared on screen with the brackets. The fix swapped ``Log`` for ``RichLog``.

These tests check two layers: (1) ``tui.py`` imports/uses ``RichLog``, and
(2) every string the TUI writes, when rendered through a plain-text Rich
console, leaves no ``[bold]``/``[/yellow]`` fragments behind.
"""

from __future__ import annotations

import inspect
from io import StringIO

import pytest
from rich.console import Console

from prometheus_cli import tui, tui_commands
from prometheus_cli.bundles import classify_registry, load_registry
from prometheus_cli.hardware import HardwareReport
from prometheus_cli.models import Settings
from prometheus_cli.onboarding import OllamaStatus


def _hw(ram: int = 16, vram: int = 8, disk: int = 200) -> HardwareReport:
    return HardwareReport(
        os="Linux", architecture="x86_64", ram_gb=ram, vram_gb=vram,
        cpu_features=[], disk_free_gb=disk,
    )


def _ollama(running: bool = True, models: list[str] | None = None) -> OllamaStatus:
    return OllamaStatus(installed=True, running=running, models=models or [], install_hint="")


def _plain_render(lines: list[str]) -> str:
    console = Console(
        file=StringIO(), record=True, force_terminal=False,
        color_system=None, width=120, legacy_windows=False,
    )
    for line in lines:
        console.print(line)
    return console.export_text(clear=True, styles=False)


_LITERAL_TAG_FRAGMENTS = [
    "[bold", "[/bold", "[yellow", "[/yellow", "[cyan", "/cyan",
    "[green", "[/green", "[red", "[/red", "[dim", "[/dim",
    "[italic", "[/italic", "[magenta", "[/magenta",
]


def assert_no_literal_markup(rendered: str) -> None:
    for frag in _LITERAL_TAG_FRAGMENTS:
        assert frag not in rendered, (
            f"Literal markup fragment {frag!r} leaked into rendered TUI output. "
            f"Output was:\n{rendered}"
        )


def test_tui_module_uses_richlog_not_log():
    src = inspect.getsource(tui)
    assert "RichLog" in src, "tui.py must import RichLog to render markup correctly"
    assert "from textual.widgets import (" in src
    # Direct grep on the import block: Log should not appear as a bare widget name.
    import_match = inspect.getsource(tui).split("from textual.widgets import (", 1)[1]
    import_block = import_match.split(")", 1)[0]
    assert "Log" not in import_block.replace("RichLog", ""), (
        "tui.py still imports the markup-unaware Log widget"
    )


def test_tui_log_helper_targets_richlog():
    assert "RichLog" in inspect.getsource(tui.PrometheusApp._log)


@pytest.mark.parametrize(
    "lines_func, args",
    [
        (tui_commands.first_run_banner, (Settings(),)),
        (tui_commands.help_lines, ()),
        (tui_commands.doctor_lines, (_hw(), _ollama(models=["m1", "m2"]))),
        (tui_commands.models_lines, (_ollama(models=["granite4.1:3b"]),)),
        (tui_commands.modes_lines, ()),
        (tui_commands.tools_lines, ()),
        (tui_commands.mcp_lines, ()),
        (tui_commands.providers_lines, (Settings(local_only=True),)),
        (tui_commands.permissions_lines, (Settings(),)),
        (tui_commands.sandbox_lines, ()),
        (tui_commands.vision_lines, ()),
        (tui_commands.assets_lines, ()),
    ],
)
def test_slash_command_output_renders_without_leaking_markup(lines_func, args):
    lines = lines_func(*args)
    rendered = _plain_render(lines)
    assert_no_literal_markup(rendered)


def test_first_run_banner_renders_welcome_text_cleanly():
    rendered = _plain_render(tui_commands.first_run_banner(Settings()))
    assert "Welcome to PROMETHEUS!" in rendered
    assert_no_literal_markup(rendered)


def test_setup_lines_render_cleanly():
    classified = classify_registry(load_registry(), _hw(), [])
    rendered = _plain_render(tui_commands.setup_lines(Settings(), classified))
    assert "first-run setup" in rendered
    assert "/use" in rendered
    assert_no_literal_markup(rendered)


def test_settings_lines_render_cleanly():
    classified = classify_registry(load_registry(), _hw(), ["granite4.1:3b"])
    settings = Settings(active_bundle_id="spark-cpu-8gb")
    rendered = _plain_render(tui_commands.settings_lines(settings, classified, ["granite4.1:3b"]))
    assert "Settings" in rendered
    assert_no_literal_markup(rendered)


def test_unknown_command_message_renders_cleanly():
    msg = "[yellow]Unknown command:[/yellow] /modles. Try [bold]/help[/bold]."
    rendered = _plain_render([msg])
    assert "Unknown command:" in rendered
    assert_no_literal_markup(rendered)
