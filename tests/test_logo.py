from __future__ import annotations

from prometheus_cli import logo


def test_logo_module_exposes_temporary_marker():
    assert logo.TEMPORARY_ASCII_LOGO is True


def test_static_logo_renders_label():
    out = logo.static_logo("compact")
    assert "PROMETHEUS" in out


def test_render_logo_returns_multiline_art():
    out = logo.render_logo(0, size="normal")
    assert len(out.splitlines()) > 1


def test_should_animate_logo_respects_no_animation():
    assert logo.should_animate_logo(no_animation=True) is False


def test_logo_sizes_match_splash():
    assert set(logo.sizes()) == {"compact", "normal", "wide"}


def test_replacement_criterion_documents_placeholder():
    assert "temporary" in logo.REPLACEMENT_CRITERION.lower()
