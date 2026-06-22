from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_screens import render_screen_text, strip_markup, SLASH_SCREEN_MAP
from prometheus_cli.tui_state import collect_demo_snapshot

textual = pytest.importorskip("textual")

MIN_CONTENT_CHARS = 50
MIN_LABELS = 3
REQUIRED_LABELS_DASHBOARD = ["PROMETHEUS", "Ask", "Ollama"]


def _run(coro):
    return asyncio.run(coro)


class TestDashboardNotEmpty:
    def test_dashboard_has_substantial_content(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title="density check")
                non_tag = re.sub(r"<[^>]+>", "", svg)
                non_ws = re.sub(r"\s+", "", non_tag)
                assert len(non_ws) > 200, (
                    f"dashboard SVG has too little visible content: {len(non_ws)} chars"
                )
        _run(go())

    def test_dashboard_has_required_labels(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title="labels check")
                for label in REQUIRED_LABELS_DASHBOARD:
                    assert label in svg, f"required label '{label}' not in dashboard SVG"
        _run(go())

    def test_no_giant_empty_panel(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.15)
                main = app.query_one("#main")
                assert main is not None
                sb = app.query_one("#sidebar")
                assert sb is not None
        _run(go())


class TestScreensHaveContent:
    @pytest.mark.parametrize("cmd", [c for c in sorted(SLASH_SCREEN_MAP) if c != "/?"])
    def test_screen_text_above_threshold(self, cmd):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text(cmd, snap)
        clean = strip_markup(text)
        non_ws = len(clean.strip())
        assert non_ws >= MIN_CONTENT_CHARS, (
            f"{cmd} screen has only {non_ws} non-whitespace chars (min {MIN_CONTENT_CHARS})"
        )

    @pytest.mark.parametrize("cmd", [c for c in sorted(SLASH_SCREEN_MAP) if c != "/?"])
    def test_screen_has_multiple_lines(self, cmd):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text(cmd, snap)
        lines = [l for l in text.split("\n") if l.strip()]
        assert len(lines) >= MIN_LABELS, (
            f"{cmd} has only {len(lines)} non-empty lines (min {MIN_LABELS})"
        )


class TestNoDebugBoxAt80x24:
    def test_80x24_does_not_crash(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title="80x24")
                assert "<svg" in svg
                assert len(svg) > 3000
        _run(go())

    def test_80x24_has_visible_content(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title="80x24 content")
                non_tag = re.sub(r"<[^>]+>", "", svg)
                non_ws = re.sub(r"\s+", "", non_tag)
                assert len(non_ws) > 50, f"80x24 has too little visible text: {len(non_ws)} chars"
        _run(go())

    def test_80x24_pROMETHEUS_label_present(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title="80x24 brand")
                assert "PROMETHEUS" in svg
        _run(go())


class TestChromePresentAtNormalSize:
    @pytest.mark.parametrize("selector", [
        "#brand-header", "#sidebar", "#main", "#inspector",
        "#cmd-input", "#status-bar",
    ])
    def test_chrome_region_present(self, selector):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                w = app.query_one(selector)
                assert w is not None, f"{selector} missing"
        _run(go())
