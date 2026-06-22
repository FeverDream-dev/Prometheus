from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp

textual = pytest.importorskip("textual")


def _run(coro):
    return asyncio.run(coro)


class TestShellStructure:
    def test_all_chrome_regions_compose(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                for sel in ("#brand-header", "#sidebar", "#main", "#inspector",
                            "#cmd-input", "#status-bar"):
                    w = app.query_one(sel)
                    assert w is not None, f"{sel} missing from shell"
        _run(go())

    def test_input_has_correct_placeholder(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                inp = app.query_one("#cmd-input")
                assert "Ask PROMETHEUS" in (inp.placeholder or "")
        _run(go())

    def test_demo_ribbon_shown_in_demo_mode(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                ribbon = app.query_one("#demo-ribbon")
                assert ribbon is not None
        _run(go())

    def test_app_has_keybindings(self):
        assert any(b.key == "ctrl+p" for b in PrometheusApp.BINDINGS)
        assert any(b.key == "ctrl+b" for b in PrometheusApp.BINDINGS)
        assert any(b.key == "ctrl+q" for b in PrometheusApp.BINDINGS)

    def test_css_has_obsidian_gold_theme(self):
        css = PrometheusApp.CSS
        assert "#0b0c10" in css or "obsidian" in css.lower()
        assert "#d4a02a" in css or "gold" in css.lower()


class TestResponsiveLayout:
    def test_80x24_does_not_crash(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.12)
                assert app.size.width == 80
        _run(go())

    def test_100x30_shows_sidebar(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(100, 30)) as pilot:
                await pilot.pause(0.12)
                sb = app.query_one("#sidebar")
                assert sb.styles.display != "none"
        _run(go())

    def test_120x36_shows_both_rails(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                sb = app.query_one("#sidebar")
                insp = app.query_one("#inspector")
                assert sb.styles.display != "none"
                assert insp.styles.display != "none"
        _run(go())


class TestExitAfterRender:
    def test_exit_after_render_via_launch(self):
        from prometheus_cli.tui import _exit_after_render
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        _exit_after_render(app, initial_screen=None)
