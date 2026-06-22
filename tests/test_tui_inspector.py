from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_state import collect_demo_snapshot, TuiSnapshot

textual = pytest.importorskip("textual")

REQUIRED_CARDS = ["hardware", "provider", "bundle", "git", "sandbox", "memory"]


def _run(coro):
    return asyncio.run(coro)


class TestSnapshotData:
    def test_demo_snapshot_has_hardware(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        assert snap.ram_gb > 0
        assert snap.os
        assert snap.arch

    def test_demo_snapshot_has_ollama_status(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        assert hasattr(snap, "ollama_running")
        assert hasattr(snap, "ollama_models")

    def test_demo_snapshot_has_git_info(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        assert snap.git is not None
        assert hasattr(snap.git, "status_label")

    def test_demo_snapshot_has_memory_info(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        assert snap.memory is not None
        assert hasattr(snap.memory, "status_label")

    def test_demo_snapshot_has_sandbox_info(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        assert hasattr(snap, "sandbox_tier")

    def test_demo_snapshot_is_flagged_demo(self):
        snap = collect_demo_snapshot(Path("/tmp"))
        assert snap.is_demo is True


class TestInspectorRendering:
    def test_inspector_renders_at_normal_width(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                insp = app.query_one("#inspector")
                assert insp.styles.display != "none"
        _run(go())

    def test_inspector_collapses_at_narrow_width(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(80, 24)) as pilot:
                await pilot.pause(0.12)
                insp = app.query_one("#inspector")
                assert insp.styles.display == "none"
        _run(go())

    def test_ctrl_i_toggles_inspector(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                insp = app.query_one("#inspector")
                initial = insp.styles.display
                await pilot.press("ctrl+i")
                await pilot.pause(0.05)
                assert insp.styles.display != initial or insp.styles.display == "none"
        _run(go())

    def test_inspector_shows_hardware_card_in_demo(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                insp = app.query_one("#inspector")
                from io import StringIO
                from rich.console import Console
                console = Console(file=StringIO(), record=True, color_system=None, width=60)
                if insp._snapshot is not None:
                    rendered = insp.render_default(insp._snapshot)
                    console.print(rendered, markup=True)
                    text = console.export_text(clear=True, styles=False)
                    assert "RAM" in text or "OS" in text
        _run(go())

    def test_inspector_shows_bundle_info_in_demo(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                insp = app.query_one("#inspector")
                assert insp._snapshot is not None
                from io import StringIO
                from rich.console import Console
                console = Console(file=StringIO(), record=True, color_system=None, width=60)
                rendered = insp.render_default(insp._snapshot)
                console.print(rendered, markup=True)
                text = console.export_text(clear=True, styles=False)
                assert "Mode" in text or "Sandbox" in text or "Bundle" in text
        _run(go())

    def test_inspector_shows_git_status_in_demo(self):
        async def go():
            app = PrometheusApp(demo=True, workspace=Path("/tmp"))
            async with app.run_test(size=(120, 36)) as pilot:
                await pilot.pause(0.12)
                insp = app.query_one("#inspector")
                assert insp._snapshot is not None
                from io import StringIO
                from rich.console import Console
                console = Console(file=StringIO(), record=True, color_system=None, width=60)
                rendered = insp.render_default(insp._snapshot)
                console.print(rendered, markup=True)
                text = console.export_text(clear=True, styles=False)
                assert "Git" in text or "git" in text or "Branch" in text
        _run(go())
