"""Style profile comparison: actual CSS vs expected design profile.

The deterministic comparison is the primary pass/fail gate. Properties are
compared with configurable tolerance. A vision model may add subjective
review but cannot override the deterministic result.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .style_snapshot import StyleSnapshot


@dataclass
class PropertyDiff:
    property: str
    expected: str
    actual: str
    matched: bool
    tolerance: float = 0.0


@dataclass
class ComparisonResult:
    matched: bool
    diffs: list[PropertyDiff] = field(default_factory=list)
    contrast_ratio_actual: float | None = None
    contrast_ratio_expected: float | None = None
    contrast_passed: bool = True
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "diffs": [asdict(d) for d in self.diffs],
            "contrast_ratio_actual": self.contrast_ratio_actual,
            "contrast_ratio_expected": self.contrast_ratio_expected,
            "contrast_passed": self.contrast_passed,
            "summary": self.summary,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)


def load_profile(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _try_float(val: str) -> float | None:
    try:
        return float(val.replace("px", "").replace("rem", "").replace("em", "").strip())
    except (ValueError, AttributeError):
        return None


def _values_match(expected: str, actual: str, tolerance: float) -> bool:
    if expected.strip().lower() == actual.strip().lower():
        return True
    exp_f = _try_float(expected)
    act_f = _try_float(actual)
    if exp_f is not None and act_f is not None:
        return abs(exp_f - act_f) <= tolerance
    return False


def compare_snapshots(
    actual: StyleSnapshot,
    expected_profile: dict[str, Any],
    tolerance_px: float = 1.0,
) -> ComparisonResult:
    expected_props: dict[str, str] = expected_profile.get("properties", {})
    if not expected_props:
        expected_props = {k: str(v) for k, v in expected_profile.items()
                         if k not in ("contrast_ratio_min", "description", "name")}
    diffs: list[PropertyDiff] = []
    all_keys = sorted(set(expected_props) | set(actual.properties))
    for key in all_keys:
        if key not in expected_props:
            continue
        exp = expected_props[key]
        act = actual.properties.get(key, "")
        matched = _values_match(str(exp), str(act), tolerance_px)
        diffs.append(PropertyDiff(
            property=key, expected=str(exp), actual=str(act),
            matched=matched, tolerance=tolerance_px,
        ))

    contrast_min = expected_profile.get("contrast_ratio_min")
    actual_contrast = actual.contrast_ratio
    contrast_passed = True
    if contrast_min is not None and actual_contrast is not None:
        contrast_passed = actual_contrast >= float(contrast_min)

    mismatched = [d for d in diffs if not d.matched]
    matched = len(mismatched) == 0 and contrast_passed
    parts = []
    if mismatched:
        parts.append(f"{len(mismatched)}/{len(diffs)} properties differ")
    else:
        parts.append(f"all {len(diffs)} properties match")
    if contrast_min is not None:
        if actual_contrast is not None:
            parts.append(f"contrast {actual_contrast:.2f} vs min {contrast_min}")
        else:
            parts.append("contrast not computable")
    summary = "; ".join(parts)
    return ComparisonResult(
        matched=matched, diffs=diffs,
        contrast_ratio_actual=actual_contrast,
        contrast_ratio_expected=float(contrast_min) if contrast_min else None,
        contrast_passed=contrast_passed,
        summary=summary,
    )


__all__ = ["ComparisonResult", "PropertyDiff", "compare_snapshots", "load_profile"]
