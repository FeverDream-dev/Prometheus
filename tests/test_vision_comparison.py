from __future__ import annotations

import json
from pathlib import Path

from prometheus_cli.vision.comparison import compare_snapshots, load_profile
from prometheus_cli.vision.style_snapshot import StyleSnapshot


FIXTURE_PROFILE = {
    "name": "button-primary",
    "description": "test profile",
    "contrast_ratio_min": 4.5,
    "properties": {
        "background-color": "rgb(79, 70, 229)",
        "color": "rgb(255, 255, 255)",
        "border-radius": "6px",
        "font-size": "14px",
        "font-weight": "600",
        "cursor": "pointer",
    },
}


def _make_snapshot(props: dict, contrast: float | None = None) -> StyleSnapshot:
    snap = StyleSnapshot(properties=props)
    snap.contrast_ratio = contrast
    return snap


def test_comparison_passes_when_all_match():
    actual = _make_snapshot({
        "background-color": "rgb(79, 70, 229)",
        "color": "rgb(255, 255, 255)",
        "border-radius": "6px",
        "font-size": "14px",
        "font-weight": "600",
        "cursor": "pointer",
    }, contrast=7.0)
    result = compare_snapshots(actual, FIXTURE_PROFILE)
    assert result.matched is True
    assert len(result.diffs) == 6


def test_comparison_fails_on_mismatched_property():
    actual = _make_snapshot({
        "background-color": "rgb(255, 0, 0)",
        "color": "rgb(255, 255, 255)",
        "border-radius": "6px",
        "font-size": "14px",
        "font-weight": "600",
        "cursor": "pointer",
    }, contrast=7.0)
    result = compare_snapshots(actual, FIXTURE_PROFILE)
    assert result.matched is False
    bg_diff = [d for d in result.diffs if d.property == "background-color"]
    assert len(bg_diff) == 1
    assert bg_diff[0].matched is False


def test_comparison_fails_on_low_contrast():
    actual = _make_snapshot({
        "background-color": "rgb(79, 70, 229)",
        "color": "rgb(255, 255, 255)",
    }, contrast=2.0)
    result = compare_snapshots(actual, FIXTURE_PROFILE)
    assert result.matched is False
    assert result.contrast_passed is False


def test_comparison_tolerance_for_px_values():
    actual = _make_snapshot({
        "font-size": "14.5px",
        "border-radius": "6px",
    })
    profile = {"properties": {"font-size": "14px", "border-radius": "6px"}}
    result = compare_snapshots(actual, profile, tolerance_px=1.0)
    font_diff = [d for d in result.diffs if d.property == "font-size"][0]
    assert font_diff.matched is True


def test_comparison_result_to_json():
    actual = _make_snapshot({"color": "red"})
    result = compare_snapshots(actual, {"properties": {"color": "red"}})
    j = result.to_json()
    data = json.loads(j)
    assert data["matched"] is True


def test_load_profile_from_file(tmp_path: Path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(FIXTURE_PROFILE))
    loaded = load_profile(p)
    assert loaded["name"] == "button-primary"
    assert "properties" in loaded


def test_comparison_no_profile_props_means_all_match():
    actual = _make_snapshot({"color": "red", "background-color": "blue"})
    result = compare_snapshots(actual, {})
    assert result.matched is True


def test_comparison_extra_actual_props_ignored():
    actual = _make_snapshot({
        "color": "rgb(255, 255, 255)",
        "background-color": "rgb(79, 70, 229)",
        "border-radius": "6px",
        "font-size": "14px",
        "font-weight": "600",
        "cursor": "pointer",
        "extra-property": "something",
    }, contrast=7.0)
    result = compare_snapshots(actual, FIXTURE_PROFILE)
    assert result.matched is True
