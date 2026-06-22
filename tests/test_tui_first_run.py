"""TUI 2.0 first-run / setup wizard tests.

Verifies the first-run UX: demo ribbon visibility, setup wizard reachable via
``/setup``, all 7 wizard steps rendered, and the wizard screen is a
RichCommandScreen so it renders under both interactive and headless paths.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_state import collect_demo_snapshot


def _run(coro):
    return asyncio.run(coro)


def test_demo_mode_shows_demo_ribbon():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            ribbon = app.query_one("#demo-ribbon")
            assert str(ribbon.renderable).startswith("DEMO MODE")
    _run(go())


def test_demo_mode_badges_visible_in_header():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            badges = app.query_one("#brand-badges")
            text = str(badges.renderable) if badges.renderable else ""
            assert "DEMO" in text
            assert "Pilot" in text
            assert "ember-8gb" in text
    _run(go())


def test_setup_screen_reachable_via_slash():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text("/setup")
            await pilot.pause(0.2)
            from prometheus_cli.tui_screens import SetupScreen
            assert isinstance(app.screen, SetupScreen)
    _run(go())


def test_setup_screen_shows_all_seven_steps():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text("/setup")
            await pilot.pause(0.2)
            from textual.widgets import Static
            texts = [str(w.renderable) for w in app.screen.query(Static)]
            joined = "\n".join(t for t in texts if t)
            for i in range(1, 8):
                assert f"Step {i}" in joined, f"setup screen missing Step {i}"
            for step_name in (
                "Welcome", "Hardware", "Ollama", "Recommended bundle",
                "Confirm bundle", "Pull", "Start coding",
            ):
                assert step_name in joined, f"setup screen missing step: {step_name}"
    _run(go())


def test_setup_screen_renders_demo_hardware_in_step_2():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text("/setup")
            await pilot.pause(0.2)
            from textual.widgets import Static
            joined = "\n".join(str(w.renderable) for w in app.screen.query(Static))
            assert "Linux" in joined and "x86_64" in joined
            assert "Demo CPU" in joined
            assert "32" in joined and "GB" in joined
    _run(go())


def test_demo_snapshot_carries_realistic_bundle():
    snap = collect_demo_snapshot(Path("/tmp"))
    assert snap.bundle_id == "ember-8gb"
    assert snap.bundle_status == "active"
    assert snap.bundle_name is not None
