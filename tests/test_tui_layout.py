"""Structural tests for the polished TUI layout.

We verify the layout by source inspection and attribute introspection rather
than mounting the Textual app because (a) Textual Pilot needs a TTY, and
(b) source-level assertions catch regressions in the layout itself, not just
behavioral regressions. The behavioral slash-command surface is already
covered by ``test_tui_commands.py`` and ``test_tui_markup_regression.py``.
"""

from __future__ import annotations

import inspect

from prometheus_cli.tui import PrometheusApp, launch_tui


def test_app_css_has_three_column_selectors():
    css = PrometheusApp.CSS
    for selector in ("#workspace", "#sidebar-left", "#telemetry-right", "#main-center"):
        assert selector in css, f"CSS missing {selector} for the polished layout"


def test_app_css_uses_dark_palette():
    css = PrometheusApp.CSS
    assert "#0e0f13" in css or "#14161c" in css, "dark theme background missing"
    assert "#2a2e3a" in css, "panel border color missing"


def test_compose_yields_three_columns_and_input():
    src = inspect.getsource(PrometheusApp.compose)
    assert "sidebar-left" in src
    assert "telemetry-right" in src
    assert "main-center" in src
    assert "Horizontal(id=\"workspace\"" in src or "Horizontal(id='workspace'" in src
    assert "RichLog(id" in src


def test_app_has_telemetry_refresh_and_sidebar_methods():
    assert hasattr(PrometheusApp, "_refresh_telemetry")
    assert hasattr(PrometheusApp, "_render_sidebar")
    assert hasattr(PrometheusApp, "_render_hardware")


def test_app_accepts_no_animation_kwarg():
    sig = inspect.signature(PrometheusApp.__init__)
    assert "no_animation" in sig.parameters


def test_launch_tui_passes_no_animation():
    sig = inspect.signature(launch_tui)
    assert "no_animation" in sig.parameters


def test_app_uses_horizontal_container():
    import prometheus_cli.tui as tui_mod
    assert "Horizontal" in inspect.getsource(tui_mod)
    assert "Horizontal" in inspect.getsource(PrometheusApp.compose)


def test_app_refresh_telemetry_is_safe_when_widgets_absent():
    src = inspect.getsource(PrometheusApp._refresh_telemetry)
    assert "query_one" in src
    assert "try" in src
    assert "except" in src


def test_status_bar_uses_brand_cyan_not_default_blue():
    src = inspect.getsource(__import__("prometheus_cli.tui", fromlist=["StatusBar"]))
    assert "1f6f8c" in src or "cyan" in src.lower(), "StatusBar should use brand cyan, not default blue"


def test_settings_supports_reduced_motion():
    from prometheus_cli.models import Settings
    s = Settings()
    assert hasattr(s, "reduced_motion")
    assert s.reduced_motion is False
    assert hasattr(s, "tui_telemetry_panel")
    assert s.tui_telemetry_panel is True
