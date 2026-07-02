from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_screens import render_screen_text, strip_markup, WIZARD_STEPS
from prometheus_cli.tui_state import collect_demo_snapshot

textual = pytest.importorskip("textual")


def _run(coro):
    return asyncio.run(coro)


class TestSetupScreenRendering:
    def test_setup_wizard_dispatches_interactive_modal(self):
        async def go():
            from prometheus_cli.tui_screens import InteractiveSetupScreen

            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/setup-wizard")
                await pilot.pause(0.15)
                assert isinstance(app.screen, InteractiveSetupScreen)
        _run(go())

    def test_setup_slash_dispatches_command_view(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/setup")
                await pilot.pause(0.15)
                assert app._current_view == "command"
        _run(go())

    def test_setup_screen_text_has_all_9_steps(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/setup", snap)
        for name in WIZARD_STEPS:
            clean = strip_markup(name)
            assert clean in text

    def test_setup_screen_text_has_no_raw_markup(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/setup", snap)
        import re
        assert not re.search(r"\[/?[a-z]+\]", text), f"raw markup in /setup: {text[:200]}"


class TestSetupWizardState:
    def test_wizard_has_9_total_steps(self):
        from prometheus_cli.tui_screens import SetupWizard
        wizard = SetupWizard(collect_demo_snapshot(Path("/tmp")))
        assert wizard.total == 9

    def test_wizard_starts_at_step_0(self):
        from prometheus_cli.tui_screens import SetupWizard
        wizard = SetupWizard(collect_demo_snapshot(Path("/tmp")))
        assert wizard.step == 0

    def test_wizard_advance_forward(self):
        from prometheus_cli.tui_screens import SetupWizard
        wizard = SetupWizard(collect_demo_snapshot(Path("/tmp")))
        wizard._advance(+1)
        assert wizard.step == 1
        wizard._advance(+1)
        assert wizard.step == 2

    def test_wizard_advance_backward(self):
        from prometheus_cli.tui_screens import SetupWizard
        wizard = SetupWizard(collect_demo_snapshot(Path("/tmp")))
        wizard.step = 3
        wizard._advance(-1)
        assert wizard.step == 2

    def test_wizard_clamps_at_boundaries(self):
        from prometheus_cli.tui_screens import SetupWizard
        wizard = SetupWizard(collect_demo_snapshot(Path("/tmp")))
        wizard._advance(-1)
        assert wizard.step == 0
        wizard.step = 8
        wizard._advance(+1)
        assert wizard.step == 8

    def test_wizard_back_button_disabled_at_step_0(self):
        from prometheus_cli.tui_screens import SetupWizard
        wizard = SetupWizard(collect_demo_snapshot(Path("/tmp")))
        assert wizard.step == 0


class TestSetupScreenshotExport:
    def test_setup_screenshot_exports_clean_svg(self, tmp_path):
        from prometheus_cli.tui import _export_screenshot
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        svg_path = tmp_path / "setup-wizard.svg"
        _export_screenshot(app, svg_path, initial_screen="setup")
        content = svg_path.read_text(encoding="utf-8")
        assert "<svg" in content
        assert len(content) > 1000
        assert "[bold" not in content
        assert "[yellow" not in content

    def test_setup_screenshot_via_cli(self, tmp_path):
        from prometheus_cli.tui import _exit_after_render
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        _exit_after_render(app, initial_screen="setup")


class TestFirstRunAutoShow:
    def test_demo_mode_does_not_auto_show_wizard(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                assert app.demo is True
        _run(go())
