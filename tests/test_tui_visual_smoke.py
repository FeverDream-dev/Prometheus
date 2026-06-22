from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_screens import SLASH_SCREEN_MAP, render_screen_text, strip_markup
from prometheus_cli.tui_state import collect_demo_snapshot

textual = pytest.importorskip("textual")

REQUIRED_SCREENS = [
    "startup", "setup", "help", "models", "bundles", "bundleforge",
    "sandbox", "memory", "vision", "assets", "astronaut", "settings",
    "doctor", "mcp",
]

SCREEN_CMDS = {
    "startup": None,
    "setup": "/setup",
    "help": "/help",
    "models": "/models",
    "bundles": "/bundles",
    "bundleforge": "/bundleforge",
    "sandbox": "/sandbox",
    "memory": "/memory",
    "vision": "/vision",
    "assets": "/assets",
    "astronaut": "/astronaut",
    "settings": "/settings",
    "doctor": "/doctor",
    "mcp": "/mcp",
}


def _run(coro):
    return asyncio.run(coro)


class TestExportAllRequiredScreens:
    @pytest.mark.parametrize("name", REQUIRED_SCREENS)
    def test_screen_exports_nontrivial_svg(self, name, tmp_path):
        cmd = SCREEN_CMDS[name]
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                if cmd:
                    app._dispatch_slash_text(cmd)
                    await pilot.pause(0.2)
                svg = app.export_screenshot(title=f"PROMETHEUS — {name}")
                out = tmp_path / f"{name}.svg"
                out.write_text(svg, encoding="utf-8")
                assert "<svg" in svg, f"{name} did not produce SVG"
                assert len(svg) > 3000, f"{name} SVG too small ({len(svg)} bytes)"
        _run(go())

    def test_dashboard_svg_has_brand(self, tmp_path):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title="dashboard")
                assert "PROMETHEUS" in svg
        _run(go())

    def test_palette_exports_svg(self, tmp_path):
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


class TestExportMultipleSizes:
    @pytest.mark.parametrize("size", [(80, 24), (100, 30), (120, 36), (160, 48)])
    def test_startup_exports_at_each_size(self, size, tmp_path):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=size) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title=f"startup {size[0]}x{size[1]}")
                out = tmp_path / f"startup_{size[0]}x{size[1]}.svg"
                out.write_text(svg, encoding="utf-8")
                assert "<svg" in svg
                assert len(svg) > 3000
        _run(go())


class TestScreenTextDensity:
    @pytest.mark.parametrize("cmd", [c for c in sorted(SLASH_SCREEN_MAP) if c != "/?"])
    def test_screen_text_has_meaningful_content(self, cmd):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text(cmd, snap)
        non_ws = len(text.strip())
        word_count = len(text.split())
        assert non_ws > 10, f"{cmd} produced too little text ({non_ws} chars)"
        assert word_count >= 3, f"{cmd} has too few words ({word_count})"


class TestArtifactsDirectory:
    def test_artifacts_tui_acceptance(self, tmp_path):
        out_dir = tmp_path / "artifacts" / "tui"
        out_dir.mkdir(parents=True, exist_ok=True)
        from prometheus_cli.tui import launch_tui
        out = out_dir / "startup.svg"
        launch_tui(demo=True, screenshot_path=out, workspace=Path("/tmp"))
        assert out.exists()
        assert out.stat().st_size > 10000
