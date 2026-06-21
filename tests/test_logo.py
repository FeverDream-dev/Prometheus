from __future__ import annotations

import io
from pathlib import Path

import pytest

from prometheus_cli import logo


def test_logo_module_marker_is_now_false_after_brand_replacement():
    assert logo.TEMPORARY_ASCII_LOGO is False


def test_replacement_criterion_documents_temporary_history():
    assert "temporary" in logo.REPLACEMENT_CRITERION.lower()


def test_static_logo_renders_label():
    out = logo.static_logo("compact")
    assert "PROMETHEUS" in out


def test_static_logo_renders_tagline_when_width_allows():
    out = logo.static_logo("normal")
    assert "local-first coding agent" in out


def test_render_logo_returns_multiline_art():
    out = logo.render_logo(0, size="normal")
    assert len(out.splitlines()) > 1


def test_render_logo_has_ring_glyphs():
    out = logo.render_logo(0, size="normal", color=False)
    assert any(g in out for g in ("█", "▓", "▒", "░"))


def test_should_animate_logo_respects_no_animation():
    assert logo.should_animate_logo(no_animation=True) is False


def test_should_animate_logo_respects_reduced_motion():
    assert logo.should_animate_logo(reduced_motion=True) is False


def test_should_animate_logo_false_in_dumb_term(monkeypatch):
    monkeypatch.setenv("TERM", "dumb")
    assert logo.should_animate_logo() is False


def test_should_animate_logo_false_on_non_tty_stream():
    assert logo.should_animate_logo(stream=io.StringIO()) is False


def test_logo_sizes_match_three_tiers():
    assert set(logo.sizes()) == {"compact", "normal", "wide"}


def test_frame_count_is_twelve_for_full_palette_rotation():
    assert logo.frame_count("normal") == 12


def test_render_logo_respects_size_widths():
    compact = max(len(ln) for ln in logo.render_logo(0, size="compact").splitlines())
    normal = max(len(ln) for ln in logo.render_logo(0, size="normal").splitlines())
    wide = max(len(ln) for ln in logo.render_logo(0, size="wide").splitlines())
    assert compact < normal < wide


def test_color_frame_emits_ansi():
    out = logo.render_logo(0, size="normal", color=True)
    assert "\033[" in out


def test_no_color_frame_strips_ansi():
    out = logo.render_logo(0, size="normal", color=False)
    assert "\033[" not in out


def test_different_frames_are_actually_different():
    a = logo.render_logo(0, size="normal", color=False)
    b = logo.render_logo(3, size="normal", color=False)
    assert a != b, "rotation step did not change the rendered art"


def test_static_mark_alias_matches_static_logo():
    assert logo.static_mark("normal") == logo.static_logo("normal")


def test_preview_logo_writes_label_to_stream():
    buf = io.StringIO()
    logo.preview_logo(width=42, animated=False, color=False, stream=buf)
    out = buf.getvalue()
    assert "PROMETHEUS" in out
    assert "\033[" not in out


def test_preview_logo_animated_respects_no_animation():
    buf = io.StringIO()
    logo.preview_logo(width=42, animated=True, no_animation=True, color=True, stream=buf)
    out = buf.getvalue()
    assert "PROMETHEUS" in out
    assert "\033[" not in out


def test_generate_logo_with_real_image(tmp_path):
    src = Path(__file__).resolve().parent.parent / "assets" / "branding" / "feverducation.png"
    if not src.exists():
        pytest.skip("company logo image not present in this checkout")
    out_path = tmp_path / "generated_logo.py"
    ok, message = logo.generate_logo(source=src, out_path=out_path)
    assert out_path.exists(), message
    content = out_path.read_text(encoding="utf-8")
    assert "GENERATED_LOGO" in content
    assert "PROMETHEUS" in content
    if ok:
        assert "local-first coding agent" in content


def test_generate_logo_missing_source(tmp_path):
    ok, message = logo.generate_logo(
        source=tmp_path / "does_not_exist.png",
        out_path=tmp_path / "out.py",
    )
    assert ok is False
    assert "not found" in message.lower()


def test_generate_logo_falls_back_when_no_pillow(tmp_path, monkeypatch):
    src = Path(__file__).resolve().parent.parent / "assets" / "branding" / "feverducation.png"
    if not src.exists():
        pytest.skip("company logo image not present")
    import sys as _sys
    monkeypatch.setitem(_sys.modules, "PIL", None)
    monkeypatch.setitem(_sys.modules, "PIL.Image", None)
    out_path = tmp_path / "fallback_logo.py"
    ok, message = logo.generate_logo(source=src, out_path=out_path)
    assert ok is False
    assert "Pillow" in message
    assert out_path.exists()
    assert "GENERATED_LOGO" in out_path.read_text(encoding="utf-8")
