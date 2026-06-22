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
            from textual.widgets import Static
            sb = app.query_one("#sidebar")
            entries = list(sb.query(Static))
            joined = " ".join(str(e.renderable) for e in entries if e.renderable)
            from prometheus_cli.tui_theme import SIDEBAR_SECTIONS
            for label, _, _ in SIDEBAR_SECTIONS:
                assert label in joined, f"sidebar missing section: {label}"
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


def test_sidebar_entries_are_clickable_widgets():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            from prometheus_cli.tui_widgets import SidebarEntry
            entries = list(app.query_one("#sidebar").query(SidebarEntry))
            assert len(entries) == 13, f"expected 13 sidebar entries, got {len(entries)}"
            cmds = [e.sidebar_cmd for e in entries]
            assert "/models" in cmds
            assert "/sandbox" in cmds
            assert "/memory" in cmds
            assert "/vision" in cmds
            assert "/assets" in cmds
            assert "/astronaut" in cmds
            assert "/settings" in cmds
    _run(go())


def test_clicking_sidebar_entry_dispatches_screen():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            from prometheus_cli.tui_widgets import SidebarEntry
            entries = list(app.query_one("#sidebar").query(SidebarEntry))
            models_entry = next(e for e in entries if e.sidebar_cmd == "/models")
            await pilot.click(models_entry)
            await pilot.pause(0.2)
            assert app._current_view == "command", (
                "clicking /models sidebar entry should show command view"
            )
            content = app.query_one("#command-content")
            text = str(content.renderable) if content.renderable else ""
            assert "Models" in text or "Ollama" in text
    _run(go())


def test_demo_transcript_shows_realistic_activity():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.15)
            svg = app.export_screenshot(title="demo transcript check")
            for keyword in ("JWT", "pytest", "PASS", "DONE"):
                assert keyword in svg, f"demo transcript missing keyword: {keyword}"
    _run(go())
