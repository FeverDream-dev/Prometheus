from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .comparison import ComparisonResult
from .element_capture import ElementCapture


def generate_report(
    capture: ElementCapture,
    comparison: ComparisonResult | None = None,
    out_dir: Path | None = None,
    url: str = "",
    profile_name: str = "",
) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "timestamp": ts,
        "url": url,
        "selector": capture.selector,
        "profile": profile_name,
        "element": capture.to_dict(),
        "comparison": comparison.to_dict() if comparison else None,
        "verdict": _verdict(capture, comparison),
    }
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        jp = out_dir / "report.json"
        jp.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        mp = out_dir / "report.md"
        mp.write_text(_markdown(report), encoding="utf-8")
    return report


def _verdict(capture: ElementCapture, comparison: ComparisonResult | None) -> str:
    if capture.error:
        return "error"
    if comparison is None:
        return "captured"
    return "pass" if comparison.matched else "fail"


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Vision Inspection Report",
        "",
        f"- **Timestamp:** {report['timestamp']}",
        f"- **URL:** {report.get('url', 'N/A')}",
        f"- **Selector:** `{report['selector']}`",
        f"- **Profile:** {report.get('profile', 'N/A')}",
        f"- **Verdict:** `{report['verdict']}`",
        "",
    ]
    elem = report.get("element", {})
    a11y = elem.get("accessibility", {})
    if a11y:
        lines.append("## Accessibility")
        lines.append(f"- Role: `{a11y.get('role', '?')}`")
        lines.append(f"- Name: {a11y.get('name', '?')}")
        lines.append(f"- Tag: `{a11y.get('tagName', '?')}`")
        lines.append(f"- Disabled: {a11y.get('disabled', False)}")
        lines.append(f"- Hidden: {a11y.get('hidden', False)}")
        lines.append("")

    comp = report.get("comparison")
    if comp:
        lines.append("## Style Comparison")
        lines.append(f"- Summary: {comp['summary']}")
        lines.append(f"- Matched: `{comp['matched']}`")
        lines.append("")
        diffs = [d for d in comp.get("diffs", []) if not d["matched"]]
        if diffs:
            lines.append("### Mismatches")
            lines.append("| Property | Expected | Actual |")
            lines.append("|---|---|---|")
            for d in diffs:
                lines.append(f"| `{d['property']}` | `{d['expected']}` | `{d['actual']}` |")
            lines.append("")
    snaps = elem.get("snapshots", {})
    if snaps and "normal" in snaps:
        lines.append("## Computed Style (normal)")
        normal = snaps["normal"].get("properties", {})
        if isinstance(normal, dict):
            for k in sorted(normal):
                lines.append(f"- `{k}`: `{normal[k]}`")
        lines.append("")
    lines.append("## Artifacts")
    lines.append("- `element.png` — element-only screenshot")
    lines.append("- `style.json` — computed CSS per state")
    lines.append("- `accessibility.json` — role/name/state")
    if comp:
        lines.append("- `comparison.json` — deterministic diff")
    return "\n".join(lines) + "\n"


__all__ = ["generate_report"]
