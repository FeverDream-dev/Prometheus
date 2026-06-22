"""TUI 2.0 snapshot tests — golden text fixtures for deterministic screens.

These use :func:`prometheus_cli.tui_screens.render_screen_text` which is a pure
function (no Textual run) that produces a plain-text dump of any command screen.
The output is compared against committed golden fixtures in tests/golden/tui/.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from prometheus_cli.tui_screens import SLASH_SCREEN_MAP, render_screen_text
from prometheus_cli.tui_state import collect_demo_snapshot

GOLDEN_DIR = Path(__file__).parent / "golden" / "tui"


@pytest.fixture(scope="module")
def snap():
    return collect_demo_snapshot(Path("/tmp"))


@pytest.mark.parametrize("cmd", sorted(SLASH_SCREEN_MAP.keys()))
def test_render_screen_text_is_nonempty(cmd, snap):
    text = render_screen_text(cmd, snap)
    assert text.strip(), f"{cmd} rendered empty body"
    assert len(text.splitlines()) >= 2, f"{cmd} too short"


@pytest.mark.parametrize("cmd", sorted(SLASH_SCREEN_MAP.keys()))
def test_render_screen_text_has_no_raw_markup(cmd, snap):
    import re
    text = render_screen_text(cmd, snap)
    assert not re.search(r"\[/?[a-z]+\]", text), (
        f"{cmd} leaked raw markup tags into rendered text"
    )
    for frag in ("[bold", "[yellow", "[/bold]", "[/]", "[cyan", "[green", "[red"):
        assert frag not in text, f"{cmd} contains literal {frag!r}"


@pytest.mark.parametrize("cmd,keyword", [
    ("/help", "Setup"),
    ("/models", "Ollama"),
    ("/sandbox", "enforcement"),
    ("/memory", "memory"),
    ("/vision", "Playwright"),
    ("/assets", "AssetForge"),
    ("/astronaut", "Astronaut"),
    ("/doctor", "OS"),
    ("/bundles", "Package"),
    ("/settings", "Settings"),
    ("/mcp", "MCP"),
    ("/tools", "Repository"),
    ("/modes", "Copilot"),
    ("/telemetry", "CPU"),
    ("/permissions", "Autonomy"),
    ("/plan", "objective"),
])
def test_render_screen_text_contains_expected_keyword(cmd, keyword, snap):
    text = render_screen_text(cmd, snap)
    assert keyword.lower() in text.lower(), (
        f"{cmd} body missing expected keyword {keyword!r} (case-insensitive)"
    )


def test_startup_golden_fixture_stable(snap):
    fixture = GOLDEN_DIR / "startup.txt"
    assert fixture.exists(), "golden fixture tests/golden/tui/startup.txt missing"
    expected = fixture.read_text(encoding="utf-8").rstrip()
    actual = render_screen_text("/help", snap).rstrip()
    assert actual == expected, (
        "startup golden fixture drifted. If intentional, regenerate via:\n"
        "  python -c \"from prometheus_cli.tui_screens import render_screen_text; "
        "from prometheus_cli.tui_state import collect_demo_snapshot; from pathlib import Path; "
        "print(render_screen_text('/help', collect_demo_snapshot(Path('/tmp'))))\" "
        "> tests/golden/tui/startup.txt"
    )


def test_help_golden_fixture_stable(snap):
    fixture = GOLDEN_DIR / "help.txt"
    assert fixture.exists(), "golden fixture tests/golden/tui/help.txt missing"
    expected = fixture.read_text(encoding="utf-8").rstrip()
    actual = render_screen_text("/help", snap).rstrip()
    assert actual == expected


def test_setup_golden_fixture_stable(snap):
    fixture = GOLDEN_DIR / "setup.txt"
    assert fixture.exists(), "golden fixture tests/golden/tui/setup.txt missing"
    expected = fixture.read_text(encoding="utf-8").rstrip()
    actual = render_screen_text("/setup", snap).rstrip()
    assert actual == expected


def test_demo_snapshot_has_realistic_data():
    snap = collect_demo_snapshot(Path("/tmp"))
    assert snap.is_demo is True
    assert snap.bundle_id == "ember-8gb"
    assert snap.mode == "pilot"
    assert snap.sandbox_tier == "basic"
    assert snap.git.branch == "main"
    assert snap.git.dirty is False
    assert snap.memory.ok is True
    assert len(snap.ollama_models) == 3
    assert snap.ollama_running is True
