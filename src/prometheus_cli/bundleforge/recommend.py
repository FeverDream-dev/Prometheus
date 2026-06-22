from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..hardware import HardwareReport
from ..resources import get_resource_root
from .catalog import ModelCatalog, load_catalog
from .schema import ForgeBundle, load_forge_bundle

KEYWORD_MAP: dict[str, list[str]] = {
    "game_development": ["game", "unity", "godot", "unreal", "sprite", "2d game", "3d game", "game dev"],
    "asset_generation": ["image", "icon", "sprite", "asset", "art", "texture", "generate image", "picture"],
    "mcp_automation": ["whatsapp", "mcp", "telegram", "slack", "discord", "message", "automate", "bot"],
    "rag_documents": ["rag", "document", "docs", "knowledge base", "search", "embed", "pdf", "semantic"],
    "qa_testing": ["qa", "test", "browser", "selenium", "playwright", "ui test", "e2e"],
    "web_development": ["web", "webapp", "website", "frontend", "backend", "api", "react", "vue", "django"],
    "cpu_only": ["cpu", "slow", "low memory", "laptop", "old machine", "no gpu", "emergency"],
    "cloud_hybrid": ["cloud", "hybrid", "openai", "anthropic", "maximum quality", "best quality"],
}

USE_CASE_TO_TEMPLATE: dict[str, str] = {
    "game_development": "game-dev-lite",
    "asset_generation": "assetforge-icon-factory",
    "mcp_automation": "whatsapp-mcp-assistant",
    "rag_documents": "rag-docs-local",
    "qa_testing": "qa-browser-vision",
    "web_development": "webapp-local-lite",
    "cpu_only": "cpu-only-emergency",
    "cloud_hybrid": "cloud-hybrid-max",
}

QUALITY_UPGRADES: dict[str, str] = {
    "web_development": "webapp-12gb-quality",
    "game_development": "game-dev-assetforge",
}


@dataclass
class RecommendationResult:
    use_case: str
    template_id: str
    bundle: ForgeBundle
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    hardware_fit: bool = True
    fit_reasons: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    license_warnings: list[str] = field(default_factory=list)


def _match_use_case(request: str) -> tuple[str, list[str]]:
    text = request.lower()
    scores: dict[str, list[str]] = {}
    for use_case, keywords in KEYWORD_MAP.items():
        matched = [kw for kw in keywords if kw in text]
        if matched:
            scores[use_case] = matched
    if not scores:
        return "web_development", []
    best = max(scores, key=lambda uc: len(scores[uc]))
    return best, scores[best]


def _templates_dir() -> Path:
    return get_resource_root() / "bundleforge"


def load_template(template_id: str) -> ForgeBundle:
    path = _templates_dir() / f"{template_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"template not found: {template_id} ({path})")
    return load_forge_bundle(path)


def list_templates() -> list[str]:
    d = _templates_dir()
    if not d.is_dir():
        return []
    return sorted(p.stem for p in d.glob("*.yaml"))


def _check_hardware_fit(bundle: ForgeBundle, ram_gb: float, vram_gb: float) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    if bundle.requirements.min_ram_gb > ram_gb:
        ok = False
        reasons.append(f"Needs {bundle.requirements.min_ram_gb} GB RAM; you have {ram_gb:.0f} GB")
    if bundle.requirements.min_vram_gb > vram_gb:
        ok = False
        reasons.append(f"Needs {bundle.requirements.min_vram_gb} GB VRAM; you have {vram_gb:.0f} GB")
    if ok:
        reasons.append(f"Fits {ram_gb:.0f} GB RAM, {vram_gb:.0f} GB VRAM")
    return ok, reasons


def _check_licenses(bundle: ForgeBundle, catalog: ModelCatalog) -> list[str]:
    warnings: list[str] = []
    for model_id in bundle.all_model_ids:
        entry = catalog.by_id(model_id)
        if entry is None:
            warnings.append(f"Model '{model_id}' not in catalog — verify license manually")
        elif not entry.commercial_safe and bundle.commercial_safe:
            warnings.append(
                f"Model '{model_id}' is marked non-commercial ({entry.license}) "
                f"but bundle claims commercial_safe"
            )
    return warnings


def recommend(
    request: str,
    hardware: HardwareReport | None = None,
    prefer_quality: bool = False,
    commercial_safe_only: bool = True,
    catalog: ModelCatalog | None = None,
) -> RecommendationResult:
    cat = catalog or load_catalog()
    use_case, matched = _match_use_case(request)
    template_id = USE_CASE_TO_TEMPLATE.get(use_case, "webapp-local-lite")

    if prefer_quality and use_case in QUALITY_UPGRADES:
        upgraded = QUALITY_UPGRADES[use_case]
        if upgraded in list_templates():
            template_id = upgraded

    bundle = load_template(template_id)
    confidence = min(1.0, len(matched) / 3.0) if matched else 0.3

    fit_ok, fit_reasons = True, ["Hardware not checked"]
    if hardware is not None:
        fit_ok, fit_reasons = _check_hardware_fit(bundle, hardware.ram_gb, hardware.vram_gb)
        if not fit_ok:
            alt_use_case = "cpu_only" if use_case != "cpu_only" else "web_development"
            alt_template_id = USE_CASE_TO_TEMPLATE.get(alt_use_case, "cpu-only-emergency")
            if alt_template_id in list_templates() and alt_template_id != template_id:
                alt_bundle = load_template(alt_template_id)
                alt_ok, _ = _check_hardware_fit(alt_bundle, hardware.ram_gb, hardware.vram_gb)
                if alt_ok:
                    bundle = alt_bundle
                    template_id = alt_template_id
                    fit_ok = True
                    fit_reasons.append(f"Switched to lighter alternative: {template_id}")

    license_warnings = _check_licenses(bundle, cat)

    alternatives = [t for t in list_templates() if t != template_id]

    return RecommendationResult(
        use_case=use_case,
        template_id=template_id,
        bundle=bundle,
        confidence=confidence,
        matched_keywords=matched,
        hardware_fit=fit_ok,
        fit_reasons=fit_reasons,
        alternatives=alternatives,
        license_warnings=license_warnings,
    )


def search_bundles(query: str, catalog: ModelCatalog | None = None) -> list[dict]:
    cat = catalog or load_catalog()
    text = query.lower()
    results: list[dict] = []
    for template_id in list_templates():
        try:
            bundle = load_template(template_id)
        except Exception:
            continue
        score = 0
        desc_lower = (bundle.name + " " + bundle.description + " " + bundle.use_case).lower()
        for word in text.split():
            if len(word) > 2 and word in desc_lower:
                score += 1
        for kw_list in KEYWORD_MAP.values():
            for kw in kw_list:
                if kw in text and kw in desc_lower:
                    score += 2
        if score > 0:
            results.append({
                "template_id": template_id,
                "name": bundle.name,
                "description": bundle.description,
                "use_case": bundle.use_case,
                "score": score,
            })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


__all__ = [
    "KEYWORD_MAP",
    "QUALITY_UPGRADES",
    "RecommendationResult",
    "USE_CASE_TO_TEMPLATE",
    "list_templates",
    "load_template",
    "recommend",
    "search_bundles",
]
