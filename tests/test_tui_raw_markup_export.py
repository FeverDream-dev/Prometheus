from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp, launch_tui
from prometheus_cli.tui_screens import SLASH_SCREEN_MAP, render_screen_text, strip_markup
from prometheus_cli.tui_state import collect_demo_snapshot

textual = pytest.importorskip("textual")

RAW_MARKUP_TAGS = [
    "[bold",
    "[/bold]",
    "[yellow",
    "[/yellow]",
    "[red",
    "[/red]",
    "[green",
    "[/green]",
    "[cyan",
    "[/cyan]",
    "[dim]",
    "[/dim]",
    "[/]",
    "[section]",
    "[gold]",
    "[k]",
    "[v]",
    "[ok]",
    "[warn]",
    "[err]",
    "[info]",
]

_MARKUP_TAG_RE = re.compile(r"\[/?[a-z_]+\]")


def _run(coro):
    return asyncio.run(coro)


def _assert_no_raw_markup(text: str, context: str = ""):
    for tag in RAW_MARKUP_TAGS:
        assert tag not in text, (
            f"Raw markup '{tag}' found in {context}"
        )
    leaks = _MARKUP_TAG_RE.findall(text)
    assert not leaks, f"Markup tags leaked in {context}: {leaks}"


class TestSvgExportNoMarkup:
    def test_dashboard_svg_no_markup(self, tmp_path):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.15)
                svg = app.export_screenshot(title="markup check")
                _assert_no_raw_markup(svg, "dashboard SVG")
        _run(go())

    def test_setup_svg_no_markup(self, tmp_path):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/setup")
                await pilot.pause(0.2)
                svg = app.export_screenshot(title="setup markup check")
                _assert_no_raw_markup(svg, "setup SVG")
        _run(go())

    def test_bundleforge_svg_no_markup(self, tmp_path):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/bundleforge")
                await pilot.pause(0.2)
                svg = app.export_screenshot(title="bundleforge markup check")
                _assert_no_raw_markup(svg, "bundleforge SVG")
        _run(go())

    @pytest.mark.parametrize("cmd", [
        "/help", "/models", "/bundles", "/sandbox", "/memory",
        "/vision", "/assets", "/astronaut", "/doctor", "/settings",
        "/mcp", "/plan",
    ])
    def test_screen_svg_no_markup(self, cmd):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text(cmd)
                await pilot.pause(0.2)
                svg = app.export_screenshot(title=f"{cmd} markup check")
                _assert_no_raw_markup(svg, f"{cmd} SVG")
        _run(go())


class TestTextExportNoMarkup:
    @pytest.mark.parametrize("cmd", sorted(c for c in SLASH_SCREEN_MAP if c != "/?"))
    def test_render_screen_text_no_markup(self, cmd):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text(cmd, snap)
        _assert_no_raw_markup(text, f"render_screen_text('{cmd}')")

    def test_strip_markup_removes_all_tags(self):
        test_cases = [
            "[bold]hello[/bold]",
            "[gold]title[/]",
            "[k]key[/] [v]value[/]",
            "[section]Header[/section]",
            "plain text no tags",
        ]
        for tc in test_cases:
            result = strip_markup(tc)
            _assert_no_raw_markup(result, f"strip_markup({tc!r})")


class TestLaunchTuiScreenshot:
    def test_launch_tui_svg_no_markup(self, tmp_path):
        out = tmp_path / "launch.svg"
        launch_tui(demo=True, screenshot_path=out, workspace=Path("/tmp"))
        svg = out.read_text(encoding="utf-8")
        _assert_no_raw_markup(svg, "launch_tui SVG")

    def test_launch_tui_setup_svg_no_markup(self, tmp_path):
        out = tmp_path / "setup.svg"
        launch_tui(
            demo=True, screenshot_path=out, workspace=Path("/tmp"),
            initial_screen="setup",
        )
        svg = out.read_text(encoding="utf-8")
        _assert_no_raw_markup(svg, "launch_tui setup SVG")

    def test_launch_tui_bundleforge_svg_no_markup(self, tmp_path):
        out = tmp_path / "bundleforge.svg"
        launch_tui(
            demo=True, screenshot_path=out, workspace=Path("/tmp"),
            initial_screen="bundleforge",
        )
        svg = out.read_text(encoding="utf-8")
        _assert_no_raw_markup(svg, "launch_tui bundleforge SVG")


class TestExportedArtifactsGrep:
    def test_no_markup_in_exported_artifacts(self, tmp_path):
        out_dir = tmp_path / "artifacts" / "tui"
        out_dir.mkdir(parents=True, exist_ok=True)
        screens = [None, "/setup", "/help", "/models", "/bundles",
                    "/bundleforge", "/sandbox", "/memory", "/doctor"]
        for cmd in screens:
            name = (cmd or "startup").strip("/")
            out = out_dir / f"{name}.svg"
            launch_tui(
                demo=True, screenshot_path=out, workspace=Path("/tmp"),
                initial_screen=cmd.strip("/") if cmd else None,
            )
        for svg_file in out_dir.glob("*.svg"):
            content = svg_file.read_text(encoding="utf-8")
            _assert_no_raw_markup(content, f"{svg_file.name}")
