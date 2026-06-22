"""TUI 2.0 layout tests — verifies the application chrome composes correctly.

Covers the structural acceptance criteria: brand header, sidebar with all 13
sections, inspector panel, command input, dense status bar with all 6 segments,
and the input placeholder copy.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from prometheus_cli.tui import PrometheusApp


def _run(coro):
    return asyncio.run(coro)


def test_compose_yields_all_chrome_regions():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            for selector in ("#brand-header", "#sidebar", "#main", "#inspector",
                             "#cmd-input", "#status-bar"):
                w = app.query_one(selector)
                assert w is not None, f"{selector} missing"
    _run(go())


def test_css_uses_obsidian_background_and_gold_accent():
    css = PrometheusApp.CSS
    assert "#0b0c10" in css, "obsidian background missing"
    assert "#d4a02a" in css, "warm gold accent missing"
    assert "#5b4a2a" in css, "bronze border missing"
    assert "#ff00ff" not in css, "no clown magenta"
    assert "linear-gradient" not in css, "no generic purple gradient"


def test_sidebar_lists_all_required_sections():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            sb = app.query_one("#sidebar")
            from prometheus_cli.tui_theme import SIDEBAR_SECTIONS
            rendered = sb.renderable
            rendered_str = str(rendered) if rendered else ""
            for label, _, _ in SIDEBAR_SECTIONS:
                assert label in rendered_str, f"sidebar missing section: {label}"
    _run(go())


def test_status_bar_shows_six_segments():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            bar = app.query_one("#status-bar")
            rendered = bar.renderable
            text = str(rendered) if rendered else ""
            for seg in ("provider", "bundle", "mode", "sandbox", "git", "memory"):
                assert seg in text, f"status bar missing segment: {seg}"
    _run(go())


def test_input_placeholder_mentions_build_fix_test_explain():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            inp = app.query_one("#cmd-input")
            ph = inp.placeholder
            for word in ("build", "fix", "test", "explain"):
                assert word in ph, f"input placeholder missing word: {word}"
    _run(go())


def test_app_has_brand_header_with_logo_and_project():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            header = app.query_one("#brand-mark")
            rendered = str(header.renderable) if header.renderable else ""
            assert "PROMETHEUS" in rendered
    _run(go())
