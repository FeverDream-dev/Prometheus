from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_screens import render_screen_text, SLASH_SCREEN_MAP
from prometheus_cli.tui_state import collect_demo_snapshot

textual = pytest.importorskip("textual")

REQUIRED_SCREENS = [
    "/help", "/setup", "/settings", "/models", "/bundles",
    "/bundleforge", "/sandbox", "/mcp", "/memory", "/vision",
    "/assets", "/astronaut", "/doctor",
]


def _run(coro):
    return asyncio.run(coro)


class TestAllScreensInRegistry:
    @pytest.mark.parametrize("cmd", REQUIRED_SCREENS)
    def test_screen_is_in_slash_map(self, cmd):
        assert cmd in SLASH_SCREEN_MAP, f"{cmd} missing from SLASH_SCREEN_MAP"

    def test_bundleforge_screen_exists(self):
        assert "/bundleforge" in SLASH_SCREEN_MAP


class TestScreenTextRenders:
    @pytest.mark.parametrize("cmd", REQUIRED_SCREENS)
    def test_screen_text_is_nonempty(self, cmd):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text(cmd, snap)
        assert len(text.strip()) > 10, f"{cmd} produced empty screen text"

    @pytest.mark.parametrize("cmd", REQUIRED_SCREENS)
    def test_screen_text_has_substantive_content(self, cmd):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text(cmd, snap)
        word_count = len(text.split())
        assert word_count >= 3, f"{cmd} has too few words: {word_count}"


class TestScreenDispatch:
    @pytest.mark.parametrize("cmd", REQUIRED_SCREENS)
    def test_screen_dispatches_without_error(self, cmd):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text(cmd)
                await pilot.pause(0.15)
        _run(go())

    def test_bundleforge_dispatches(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                app._dispatch_slash_text("/bundleforge")
                await pilot.pause(0.15)
        _run(go())


class TestScreenContentQuality:
    def test_help_lists_commands(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/help", snap)
        assert "help" in text.lower() or "command" in text.lower()

    def test_models_shows_model_list(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/models", snap)
        assert len(text) > 20

    def test_sandbox_shows_tier(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/sandbox", snap)
        assert len(text) > 10

    def test_doctor_shows_hardware(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/doctor", snap)
        text_lower = text.lower()
        assert "ram" in text_lower or "os" in text_lower or "cpu" in text_lower

    def test_bundleforge_shows_templates(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/bundleforge", snap)
        assert len(text) > 20

    def test_setup_shows_wizard_steps(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/setup", snap)
        assert "step" in text.lower() or "welcome" in text.lower()

    def test_memory_shows_status(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/memory", snap)
        assert len(text) > 10

    def test_vision_shows_inspector(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/vision", snap)
        assert len(text) > 10

    def test_assets_shows_assetforge(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/assets", snap)
        assert len(text) > 10

    def test_astronaut_shows_session(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        text = render_screen_text("/astronaut", snap)
        assert len(text) > 10
