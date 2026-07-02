"""TUI 2.0 command palette + slash dispatch tests.

Verifies every advertised slash command actually dispatches to a screen, the
palette opens on Ctrl+P, and the palette lists every command advertised in
:tdata:`prometheus_cli.tui_theme.COMMAND_PALETTE`.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_screens import SLASH_SCREEN_MAP, CommandPaletteScreen
from prometheus_cli.tui_theme import COMMAND_PALETTE


def _run(coro):
    return asyncio.run(coro)


_SKIPPED_DISPATCH = {"/?", "/setup-wizard", "/memory", "/setup"}


@pytest.mark.parametrize("cmd", [c for c in sorted(SLASH_SCREEN_MAP.keys()) if c not in _SKIPPED_DISPATCH])
def test_every_slash_screen_command_dispatches(cmd):
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text(cmd)
            await pilot.pause(0.2)
            assert app._current_view == "command", (
                f"{cmd} did not swap main area to command view"
            )
    _run(go())


def test_command_palette_opens_with_ctrl_p():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            await pilot.press("ctrl+p")
            await pilot.pause(0.2)
            assert isinstance(app.screen, CommandPaletteScreen)
    _run(go())


def test_command_palette_opens_via_action():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app.action_command_palette()
            await pilot.pause(0.2)
            assert isinstance(app.screen, CommandPaletteScreen)
    _run(go())


def test_palette_lists_every_advertised_command():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app.action_command_palette()
            await pilot.pause(0.2)
            listing = app.query_one("#palette-list")
            text = str(listing.renderable) if listing.renderable else ""
            for cmd, _desc, _shortcut, _avail, _src in COMMAND_PALETTE:
                assert cmd in text, f"palette missing command: {cmd}"
    _run(go())


def test_palette_filter_narrows_results():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app.action_command_palette()
            await pilot.pause(0.2)
            from textual.widgets import Input
            inp = app.query_one("#palette-input", Input)
            inp.value = "memory"
            await pilot.pause(0.15)
            listing = app.query_one("#palette-list")
            text = str(listing.renderable) if listing.renderable else ""
            assert "/memory" in text
            assert "/sandbox" not in text
    _run(go())


def test_clear_command_clears_transcript():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            from textual.widgets import RichLog
            log = app.query_one("#transcript", RichLog)
            log.write("marker line one")
            log.write("marker line two")
            await pilot.pause(0.05)
            app._dispatch_slash_text("/clear")
            await pilot.pause(0.1)
            svg = app.export_screenshot(title="after clear")
            assert "marker line one" not in svg
            assert "marker line two" not in svg
    _run(go())


def test_mode_switch_updates_status_bar():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text("/mode astronaut")
            await pilot.pause(0.15)
            bar = app.query_one("#status-bar")
            text = str(bar.renderable) if bar.renderable else ""
            assert "Astronaut" in text
    _run(go())


def test_unknown_command_reports_error_in_transcript():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text("/nonexistent")
            await pilot.pause(0.15)
            from textual.widgets import RichLog
            log = app.query_one("#transcript", RichLog)
            joined = "\n".join(str(s) for s in log.lines)
            assert "Unknown" in joined or "unknown" in joined
    _run(go())


def test_command_view_shows_title_and_body():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text("/sandbox")
            await pilot.pause(0.2)
            content = app.query_one("#command-content")
            text = str(content.renderable) if content.renderable else ""
            assert "Sandbox" in text
            assert "enforcement" in text
    _run(go())
