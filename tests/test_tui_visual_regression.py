"""TUI 2.0 visual regression tests — SVG export smoke for every screen.

Drives the app in demo mode, pushes each command screen, exports an SVG, and
asserts it's a non-trivial renderable SVG. Also exercises the
``prometheus tui --screenshot`` CLI path via :func:`launch_tui`.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp, launch_tui
from prometheus_cli.tui_screens import SLASH_SCREEN_MAP


def _run(coro):
    return asyncio.run(coro)


def test_export_dashboard_svg(tmp_path):
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.15)
            svg = app.export_screenshot(title="dashboard smoke")
            out = tmp_path / "dashboard.svg"
            out.write_text(svg, encoding="utf-8")
            assert "<svg" in svg
            assert len(svg) > 50000
            assert "PROMETHEUS" in svg
    _run(go())


@pytest.mark.parametrize("cmd", [c for c in sorted(SLASH_SCREEN_MAP.keys()) if c != "/?"])
def test_export_every_screen_svg(cmd):
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text(cmd)
            await pilot.pause(0.2)
            svg = app.export_screenshot(title=f"{cmd}")
            assert "<svg" in svg, f"{cmd} did not produce SVG"
            assert len(svg) > 3000, f"{cmd} SVG too small ({len(svg)} bytes)"
    _run(go())


def test_palette_screen_exports_svg():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app.action_command_palette()
            await pilot.pause(0.2)
            svg = app.export_screenshot(title="palette")
            assert "<svg" in svg
            assert len(svg) > 3000
    _run(go())


def test_screenshot_path_via_launch_tui(tmp_path):
    out = tmp_path / "launch.svg"
    launch_tui(demo=True, screenshot_path=out, workspace=Path("/tmp"))
    assert out.exists(), "screenshot file not created"
    svg = out.read_text(encoding="utf-8")
    assert "<svg" in svg
    assert len(svg) > 10000
    assert "PROMETHEUS" in svg


def test_screenshot_with_initial_screen(tmp_path):
    out = tmp_path / "setup.svg"
    launch_tui(
        demo=True, screenshot_path=out, workspace=Path("/tmp"),
        initial_screen="setup",
    )
    assert out.exists()
    svg = out.read_text(encoding="utf-8")
    assert "<svg" in svg
    assert len(svg) > 5000


def test_artifacts_dir_acceptance(tmp_path):
    """Spec requirement: visual smoke artifacts go to artifacts/tui/."""
    out_dir = tmp_path / "artifacts" / "tui"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "startup.svg"
    launch_tui(demo=True, screenshot_path=out, workspace=Path("/tmp"))
    assert out.exists()
    assert out.stat().st_size > 10000
