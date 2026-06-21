from __future__ import annotations

from prometheus_cli.vision.style_snapshot import (
    BoundingBox,
    StyleSnapshot,
    build_snapshot,
    compute_contrast_ratio,
    SNAPSHOT_PROPERTIES,
)


def test_snapshot_properties_is_frozen_tuple():
    assert isinstance(SNAPSHOT_PROPERTIES, tuple)
    assert "background-color" in SNAPSHOT_PROPERTIES
    assert "color" in SNAPSHOT_PROPERTIES
    assert "font-size" in SNAPSHOT_PROPERTIES


def test_build_snapshot_extracts_properties():
    raw = {
        "background-color": "rgb(79, 70, 229)",
        "color": "rgb(255, 255, 255)",
        "font-size": "14px",
        "bounding_box": {"x": 10, "y": 20, "width": 80, "height": 36,
                         "top": 20, "right": 90, "bottom": 56, "left": 10},
    }
    snap = build_snapshot(raw, state="normal")
    assert snap.state == "normal"
    assert snap.properties["background-color"] == "rgb(79, 70, 229)"
    assert snap.properties["color"] == "rgb(255, 255, 255)"
    assert snap.bounding_box is not None
    assert snap.bounding_box.width == 80


def test_build_snapshot_computes_contrast():
    raw = {
        "background-color": "rgb(0, 0, 0)",
        "color": "rgb(255, 255, 255)",
    }
    snap = build_snapshot(raw)
    assert snap.contrast_ratio is not None
    assert snap.contrast_ratio >= 20.0


def test_contrast_white_on_indigo_meets_wcag_aa():
    ratio = compute_contrast_ratio("rgb(255, 255, 255)", "rgb(79, 70, 229)")
    assert ratio is not None
    assert ratio >= 4.5


def test_contrast_returns_none_for_invalid():
    assert compute_contrast_ratio("notacolor", "rgb(0,0,0)") is None
    assert compute_contrast_ratio("", "rgb(0,0,0)") is None


def test_contrast_hex_format():
    ratio = compute_contrast_ratio("#ffffff", "#000000")
    assert ratio is not None
    assert ratio >= 20.0


def test_contrast_short_hex():
    ratio = compute_contrast_ratio("#fff", "#000")
    assert ratio is not None
    assert ratio >= 20.0


def test_snapshot_to_json_roundtrip():
    snap = StyleSnapshot(properties={"color": "red"}, state="normal")
    j = snap.to_json()
    assert '"state": "normal"' in j
    assert '"color": "red"' in j


def test_bounding_box_to_dict():
    bb = BoundingBox(x=1, y=2, width=3, height=4)
    d = bb.to_dict()
    assert d["x"] == 1
    assert d["width"] == 3
