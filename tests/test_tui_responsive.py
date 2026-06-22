"""TUI 2.0 responsive layout tests — verifies graceful collapse at 4 sizes.

The acceptance criteria require the TUI to work at 80x24, 100x30, 120x36, and
160x48 without crashing or rendering giant empty areas. These tests instantiate
the app at each size, let it settle, export an SVG, and assert structural facts
about which panels are visible/hidden at each breakpoint.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("size", [(80, 24), (100, 30), (120, 36), (160, 48)])
def test_renders_without_crashing_at_each_size(size):
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=size) as pilot:
            await pilot.pause(0.15)
            svg = app.export_screenshot(title=f"responsive {size[0]}x{size[1]}")
            assert "<svg" in svg
            assert len(svg) > 5000
    _run(go())


def test_80x24_hides_inspector_and_sidebar():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause(0.15)
            sb = app.query_one("#sidebar")
            insp = app.query_one("#inspector")
            assert str(sb.styles.display) == "none", "sidebar should collapse at < 80"
            assert str(insp.styles.display) == "none", "inspector should collapse at < 100"
    _run(go())


def test_100x30_hides_inspector_keeps_sidebar():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause(0.15)
            sb = app.query_one("#sidebar")
            insp = app.query_one("#inspector")
            assert str(sb.styles.display) != "none", "sidebar should stay at >= 80"
            assert str(insp.styles.display) == "none", "inspector should collapse at < 100"
    _run(go())


def test_120x36_shows_sidebar_and_inspector():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.15)
            sb = app.query_one("#sidebar")
            insp = app.query_one("#inspector")
            assert str(sb.styles.display) != "none"
            assert str(insp.styles.display) != "none"
    _run(go())


def test_160x48_renders_rich_content():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(160, 48)) as pilot:
            await pilot.pause(0.15)
            svg = app.export_screenshot(title="wide")
            assert len(svg) > 50000, "wide layout should produce substantial SVG"
            assert "PROMETHEUS" in svg
    _run(go())


def test_toggle_sidebar_binding_works():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            sb = app.query_one("#sidebar")
            assert str(sb.styles.display) != "none"
            await pilot.press("ctrl+b")
            await pilot.pause(0.1)
            assert str(sb.styles.display) == "none"
            await pilot.press("ctrl+b")
            await pilot.pause(0.1)
            assert str(sb.styles.display) != "none"
    _run(go())


def test_toggle_inspector_binding_works():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            insp = app.query_one("#inspector")
            assert str(insp.styles.display) != "none"
            await pilot.press("ctrl+i")
            await pilot.pause(0.1)
            assert str(insp.styles.display) == "none"
    _run(go())
