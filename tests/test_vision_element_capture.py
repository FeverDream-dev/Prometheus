from __future__ import annotations

import json
from pathlib import Path

from prometheus_cli.vision.element_capture import ElementCapture, _b64
from prometheus_cli.vision.style_snapshot import StyleSnapshot


def test_element_capture_save_to_writes_files(tmp_path: Path):
    snap = StyleSnapshot(properties={"color": "red"}, state="normal")
    capture = ElementCapture(
        selector="button.primary",
        screenshot_b64=_b64(b"\x89PNG fake"),
        snapshots={"normal": snap},
        accessibility={"role": "button", "name": "Save", "tagName": "button"},
    )
    capture.save_to(tmp_path)
    assert (tmp_path / "element.png").exists()
    assert (tmp_path / "style.json").exists()
    assert (tmp_path / "accessibility.json").exists()
    style_data = json.loads((tmp_path / "style.json").read_text())
    assert "normal" in style_data


def test_element_capture_save_to_writes_variants(tmp_path: Path):
    capture = ElementCapture(
        selector="button",
        screenshot_b64=_b64(b"\x89PNG"),
        variants={"hover": _b64(b"\x89PNG-hover")},
    )
    capture.save_to(tmp_path)
    assert (tmp_path / "element.png").exists()
    assert (tmp_path / "element-hover.png").exists()


def test_element_capture_to_dict_summary():
    capture = ElementCapture(selector=".btn", screenshot_b64="abc123")
    d = capture.to_dict()
    assert d["selector"] == ".btn"
    assert d["has_screenshot"] is True


def test_element_capture_with_error():
    capture = ElementCapture(selector="#missing", error="element not visible")
    assert capture.error != ""
    assert capture.screenshot_b64 == ""


def test_capture_element_requires_playwright_page():
    from prometheus_cli.vision.element_capture import capture_element

    result = capture_element(page=None, selector="button")
    assert result.error != ""
