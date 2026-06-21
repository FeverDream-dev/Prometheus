from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .comparison import ComparisonResult, compare_snapshots, load_profile
from .element_capture import capture_element
from .playwright_driver import PlaywrightDriver, is_available
from .reports import generate_report
from .style_snapshot import StyleSnapshot


class VisionInspector:
    def __init__(self, headless: bool = True):
        self._headless = headless
        self._driver: PlaywrightDriver | None = None

    def inspect(
        self,
        url: str,
        selector: str | None = None,
        role: str | None = None,
        name: str | None = None,
        test_id: str | None = None,
        profile: str | Path | dict | None = None,
        variants: tuple[str, ...] = ("hover", "focus"),
        include_full_page: bool = False,
        out_dir: Path | None = None,
    ) -> dict[str, Any]:
        if not is_available():
            return {"error": "playwright not installed",
                    "hint": "pip install 'prometheus-local-agent[browser]' && playwright install chromium"}
        target_selector = selector or self._build_selector(role=role, name=name, test_id=test_id)
        if not target_selector:
            return {"error": "no element selector provided (use --selector, --role/--name, or --test-id)"}

        profile_data: dict[str, Any] | None = None
        profile_name = ""
        if profile is not None:
            if isinstance(profile, dict):
                profile_data = profile
                profile_name = profile.get("name", "inline")
            else:
                profile_data = load_profile(profile)
                profile_name = Path(profile).stem

        try:
            self._driver = PlaywrightDriver(headless=self._headless)
            self._driver.start()
            self._driver.navigate(url)
            page = self._driver.page
            capture = capture_element(
                page, target_selector,
                variants=variants, include_full_page=include_full_page,
            )
            comparison: ComparisonResult | None = None
            if profile_data and "normal" in capture.snapshots:
                comparison = compare_snapshots(capture.snapshots["normal"], profile_data)
            report = generate_report(
                capture, comparison, out_dir=out_dir,
                url=url, profile_name=profile_name,
            )
            return report
        except Exception as exc:
            return {"error": str(exc), "selector": target_selector}
        finally:
            if self._driver:
                self._driver.close()

    def compare(
        self,
        actual_path: str | Path,
        expected_path: str | Path,
    ) -> ComparisonResult:
        actual_data = json.loads(Path(actual_path).read_text(encoding="utf-8"))
        expected_data = load_profile(expected_path)
        normal_data = actual_data.get("normal", actual_data)
        props = normal_data.get("properties", normal_data)
        snap = StyleSnapshot(properties=props)
        if "contrast_ratio" in normal_data:
            snap.contrast_ratio = normal_data["contrast_ratio"]
        return compare_snapshots(snap, expected_data)

    def _build_selector(self, role: str | None, name: str | None, test_id: str | None) -> str:
        if test_id:
            return f'[data-testid="{test_id}"]'
        if role and name:
            return f'[role="{role}"]:has-text("{name}"), {role}:has-text("{name}")'
        if role:
            return f'[role="{role}"], {role}'
        return ""

    def close(self):
        if self._driver:
            self._driver.close()
            self._driver = None


def vision_doctor() -> dict[str, Any]:
    info = {
        "playwright_available": is_available(),
        "driver": None,
        "fixture_available": False,
        "vision_dir": ".prometheus/vision/",
    }
    from .playwright_driver import driver_info
    info["driver"] = driver_info()
    fixtures = Path(__file__).resolve().parent.parent.parent.parent / "tests" / "fixtures" / "web_ui"
    info["fixture_available"] = fixtures.exists()
    info["fixture_path"] = str(fixtures)
    return info


__all__ = ["VisionInspector", "vision_doctor"]
