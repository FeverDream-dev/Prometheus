"""TUI 2.0 raw-markup regression tests — no ``[bold]``, ``[yellow]``, ``[/]``
or any Rich/Textual markup may appear in rendered output.

The original TUI leaked raw markup because ``RichLog(markup=False)`` (the
default) was being fed markup-bearing strings. This file locks that fix down by
checking both the pure-text render path and the live SVG export path.
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pytest

from prometheus_cli.tui import PrometheusApp
from prometheus_cli.tui_screens import SLASH_SCREEN_MAP, render_screen_text
from prometheus_cli.tui_state import collect_demo_snapshot

_MARKUP_TAG_RE = re.compile(r"\[/?[a-z]+\]")
_LITERAL_FRAGMENTS = (
    "[bold", "[yellow", "[/bold]", "[/]", "[cyan", "[green", "[red",
    "[dim]", "[gold]", "[section]", "[k]", "[v]",
)


def _run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("cmd", sorted(SLASH_SCREEN_MAP.keys()) + ["/setup-wizard"])
def test_render_screen_text_has_no_raw_markup(cmd):
    snap = collect_demo_snapshot(Path("/tmp"))
    text = render_screen_text(cmd, snap)
    assert not _MARKUP_TAG_RE.search(text), (
        f"{cmd} leaked markup tag: {_MARKUP_TAG_RE.findall(text)}"
    )
    for frag in _LITERAL_FRAGMENTS:
        assert frag not in text, f"{cmd} contains literal {frag!r}"


def test_transcript_richlog_uses_markup_true():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.1)
            from textual.widgets import RichLog
            log = app.query_one("#transcript", RichLog)
            assert log.markup is True, (
                "RichLog must be constructed with markup=True or [bold]…[/] leaks through"
            )
    _run(go())


def test_dashboard_svg_has_no_raw_markup():
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.15)
            svg = app.export_screenshot(title="dashboard markup check")
            for frag in _LITERAL_FRAGMENTS:
                assert frag not in svg, f"dashboard SVG contains literal {frag!r}"
            assert not _MARKUP_TAG_RE.search(svg), (
                "dashboard SVG leaked markup tag"
            )
    _run(go())


@pytest.mark.parametrize("cmd", ["/help", "/setup", "/sandbox", "/memory", "/vision",
                                  "/assets", "/astronaut", "/doctor", "/bundles",
                                  "/models", "/settings", "/mcp"])
def test_pushed_screen_renders_without_raw_markup(cmd):
    async def go():
        app = PrometheusApp(demo=True, workspace=Path("/tmp"))
        async with app.run_test(size=(120, 36)) as pilot:
            await pilot.pause(0.12)
            app._dispatch_slash_text(cmd)
            await pilot.pause(0.2)
            svg = app.export_screenshot(title=f"{cmd} markup check")
            for frag in _LITERAL_FRAGMENTS:
                assert frag not in svg, f"{cmd} screen leaked {frag!r}"
    _run(go())
