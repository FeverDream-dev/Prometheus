from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_screens import InteractiveSetupScreen
from prometheus_cli.tui_widgets import SlashSuggestPanel

textual = pytest.importorskip("textual")


def _run(coro):
    return asyncio.run(coro)


class TestInteractiveSetup:
    def test_setup_opens_interactive_modal(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/setup-wizard")
                await pilot.pause(0.2)
                assert isinstance(app.screen, InteractiveSetupScreen)
        _run(go())

    def test_setup_slash_shows_command_view(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/setup")
                await pilot.pause(0.2)
                assert app._current_view == "command"
                content = app.query_one("#command-content")
                text = str(content.renderable) if content.renderable else ""
                assert "Setup" in text or "Welcome" in text
        _run(go())

    def test_bundle_click_selects_row(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 40)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/setup-wizard")
                await pilot.pause(0.2)
                screen = app.screen
                assert isinstance(screen, InteractiveSetupScreen)
                screen.select_bundle("spark-cpu-8gb")
                assert screen._selected_id == "spark-cpu-8gb"
        _run(go())


class TestSlashSuggest:
    def test_shows_commands_when_typing_slash(self):
        panel = SlashSuggestPanel()
        panel.update_prefix("/")
        assert panel.visible
        cmds = [m[0] for m in panel._matches]
        assert "/setup" in cmds

    def test_filters_as_user_types(self):
        panel = SlashSuggestPanel()
        panel.update_prefix("/set")
        assert panel.visible
        assert panel.selected_command() == "/settings" or panel.selected_command() == "/setup"


class TestSetupActions:
    def test_activate_bundle_writes_settings(self, tmp_path):
        from prometheus_cli.config import Settings
        from prometheus_cli.tui_setup_actions import activate_bundle

        settings = Settings()
        with patch("prometheus_cli.config.ensure_home", return_value=tmp_path), patch(
            "prometheus_cli.config.CONFIG_HOME", tmp_path
        ), patch("prometheus_cli.config.load_settings", return_value=settings), patch(
            "prometheus_cli.config.save_settings"
        ) as save_mock:
            ok, msg = activate_bundle("spark-cpu-8gb", home=tmp_path)
            assert ok
            assert "spark-cpu-8gb" in msg
            save_mock.assert_called_once()
            assert settings.active_bundle_id == "spark-cpu-8gb"
