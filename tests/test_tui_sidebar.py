from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_theme import SIDEBAR_SECTIONS

textual = pytest.importorskip("textual")

REQUIRED_LABELS = [
    "Chat", "Plan", "Files", "Models", "Bundles", "BundleForge",
    "Tools", "MCP", "Sandbox", "Memory", "Vision", "Assets",
    "Astronaut", "Settings",
]


def _run(coro):
    return asyncio.run(coro)


class TestSidebarSections:
    def test_config_has_all_14_required_sections(self):
        labels = [s[0] for s in SIDEBAR_SECTIONS]
        for label in REQUIRED_LABELS:
            assert label in labels, f"SIDEBAR_SECTIONS missing: {label}"

    def test_bundleforge_is_present(self):
        labels = [s[0] for s in SIDEBAR_SECTIONS]
        assert "BundleForge" in labels

    def test_bundleforge_maps_to_slash_command(self):
        entry = next(s for s in SIDEBAR_SECTIONS if s[0] == "BundleForge")
        assert entry[1] == "/bundleforge"

    def test_each_entry_has_label_cmd_blurb(self):
        for label, cmd, blurb in SIDEBAR_SECTIONS:
            assert label, "entry missing label"
            assert isinstance(cmd, str)
            assert blurb, f"{label} missing blurb"


class TestSidebarRendering:
    def test_sidebar_renders_all_labels(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                from textual.widgets import Static
                sb = app.query_one("#sidebar")
                entries = list(sb.query(Static))
                joined = " ".join(str(e.renderable) for e in entries if e.renderable)
                for label in REQUIRED_LABELS:
                    assert label in joined, f"sidebar rendering missing: {label}"
        _run(go())

    def test_sidebar_visible_at_normal_width(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                sb = app.query_one("#sidebar")
                assert sb.styles.display != "none"
        _run(go())

    def test_sidebar_collapses_at_80_width(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.12)
                sb = app.query_one("#sidebar")
                assert sb.styles.display == "none"
        _run(go())

    def test_ctrl_b_toggles_sidebar(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                sb = app.query_one("#sidebar")
                initial = sb.styles.display
                await pilot.press("ctrl+b")
                await pilot.pause(0.05)
                assert sb.styles.display != initial or sb.styles.display == "none"
        _run(go())
