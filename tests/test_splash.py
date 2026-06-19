from __future__ import annotations

import io
from pathlib import Path

import pytest

from prometheus_cli import splash
from prometheus_cli.splash_frames import FRAMES

GOLDEN_DIR = Path(__file__).parent / "golden" / "splash"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("PROMETHEUS_NO_ANIMATION", "NO_COLOR"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("TERM", "xterm")


@pytest.mark.parametrize("size", ["compact", "normal", "wide"])
def test_every_frame_has_stable_dimensions(size):
    frames = FRAMES[size]
    assert frames, f"{size} has no frames"
    heights = {len(f) for f in frames}
    widths = {len(row) for f in frames for row in f}
    assert len(heights) == 1, f"{size} frames have inconsistent line count: {heights}"
    assert len(widths) == 1, f"{size} frames have inconsistent width: {widths}"


@pytest.mark.parametrize("size", ["normal", "wide"])
def test_normal_and_wide_have_16_to_32_frames(size):
    n = splash.frame_count(size)
    assert 16 <= n <= 32, f"{size} has {n} frames, expected 16-32"


def test_compact_has_frames():
    assert splash.frame_count("compact") >= 8


def test_sizes_listed():
    assert set(splash.sizes()) == {"compact", "normal", "wide"}


def test_render_frame_nonempty_without_ansi():
    out = splash.render_frame(0, size="normal", color=False)
    assert out.strip(), "frame 0 is empty"
    assert "\033[" not in out, "color=False frame still emitted ANSI"


def test_render_frame_contains_label():
    out = splash.render_frame(0, size="compact")
    assert "PROMETHEUS" in out


def test_static_mark_compact():
    mark = splash.static_mark("compact")
    assert "PROMETHEUS" in mark
    assert mark.strip()


def test_should_animate_false_when_no_animation_flag():
    assert splash.should_animate(no_animation=True) is False


def test_should_animate_false_when_env_set(monkeypatch):
    monkeypatch.setenv("PROMETHEUS_NO_ANIMATION", "1")
    stream = io.StringIO()
    assert splash.should_animate(stream=stream) is False


def test_should_animate_false_when_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert splash.should_animate() is False


def test_should_animate_false_when_dumb_term(monkeypatch):
    monkeypatch.setenv("TERM", "dumb")
    assert splash.should_animate() is False


def test_should_animate_false_when_not_tty():
    assert splash.should_animate(stream=io.StringIO()) is False


def test_play_non_tty_emits_no_ansi():
    buf = io.StringIO()
    splash.play(size="compact", duration_s=0.1, fps=4, color=True, stream=buf)
    text = buf.getvalue()
    assert "\033[" not in text, "play emitted ANSI on a non-TTY stream"
    assert "PROMETHEUS" in text


def test_play_reduced_motion_renders_single_frame():
    buf = io.StringIO()
    splash.play(size="normal", duration_s=0.2, fps=8, reduced_motion=True, stream=buf)
    text = buf.getvalue()
    assert text.count("\n") < splash.frame_count("normal")
    assert "\033[" not in text


def test_play_respects_no_animation():
    buf = io.StringIO()
    splash.play(size="compact", no_animation=True, stream=buf)
    assert "\033[" not in buf.getvalue()


def test_color_render_uses_ansi():
    out = splash.render_frame(0, size="normal", color=True)
    assert "\033[" in out, "color=True did not emit ANSI on a clearly filled frame"


def test_pick_size_for_terminal():
    assert splash.pick_size_for_terminal(20) == "compact"
    assert splash.pick_size_for_terminal(40) == "normal"
    assert splash.pick_size_for_terminal(80) == "wide"


@pytest.mark.parametrize("size", ["compact", "normal", "wide"])
def test_golden_snapshot_first_and_last_frame(size):
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    first = splash.render_frame(0, size=size, color=False)
    last = splash.render_frame(splash.frame_count(size) - 1, size=size, color=False)
    for name, content in [(f"{size}.first.txt", first), (f"{size}.last.txt", last)]:
        path = GOLDEN_DIR / name
        if path.exists():
            assert path.read_text(encoding="utf-8") == content, f"golden drift in {name}"
        else:
            path.write_text(content, encoding="utf-8")
            pytest.fail(f"created golden {name}; re-run to confirm it is intentional")
