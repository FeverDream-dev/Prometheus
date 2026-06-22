from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp, _exit_after_render
from prometheus_cli.tui_state import collect_demo_snapshot, TuiSnapshot

textual = pytest.importorskip("textual")


def _run(coro):
    return asyncio.run(coro)


class TestDemoModeLaunches:
    def test_demo_mode_composes(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                assert app.demo is True
        _run(go())

    def test_demo_mode_shows_ribbon(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                ribbon = app.query_one("#demo-ribbon")
                from textual.widgets import Static
                assert ribbon is not None
        _run(go())

    def test_demo_snapshot_has_realistic_data(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        assert snap.ram_gb > 0
        assert snap.os
        assert len(snap.ollama_models) >= 1
        assert snap.bundle_label
        assert snap.mode_label


class TestDemoModeNoExternalDeps:
    def test_demo_mode_does_not_call_ollama(self):
        from unittest import mock
        with mock.patch("httpx.get", side_effect=AssertionError("demo mode must not call httpx")):
            snap = collect_demo_snapshot(Path("/tmp"))
            assert snap.is_demo

    def test_demo_transcript_populates(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.15)
                from textual.widgets import RichLog
                log = app.query_one("#transcript", RichLog)
                assert log is not None
        _run(go())


class TestExitAfterRender:
    def test_exit_after_render_works(self):
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        _exit_after_render(app, initial_screen=None)

    def test_exit_after_render_with_screen(self):
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        _exit_after_render(app, initial_screen="help")

    def test_exit_after_render_with_bundleforge(self):
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        _exit_after_render(app, initial_screen="bundleforge")


class TestDemoScreenshotExport:
    def test_demo_svg_export(self, tmp_path):
        from prometheus_cli.tui import _export_screenshot
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        svg_path = tmp_path / "demo.svg"
        _export_screenshot(app, svg_path, initial_screen=None)
        content = svg_path.read_text(encoding="utf-8")
        assert "<svg" in content
        assert len(content) > 1000

    def test_demo_svg_setup(self, tmp_path):
        from prometheus_cli.tui import _export_screenshot
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        svg_path = tmp_path / "setup.svg"
        _export_screenshot(app, svg_path, initial_screen="setup")
        content = svg_path.read_text(encoding="utf-8")
        assert "<svg" in content
