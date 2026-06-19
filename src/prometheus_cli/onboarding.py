"""Onboarding logic for `prometheus setup`.

Pure functions that decide which bundle fits the host are separated from the
interactive prompts so they can be unit-tested without a TTY. The setup command
never downloads a model without explicit confirmation, per PRODUCT_SPEC.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx

from .hardware import HardwareReport, recommended_profile
from .models import ModelBundle

# Conservative download-size estimates; verified against Ollama's manifest before any download.
_APPROX_DOWNLOAD_GB: dict[str, float] = {
    "gemma3:4b": 3.5,
    "qwen3:8b": 6.5,
    "qwen3:14b": 11.0,
    "qwen3-coder:latest": 9.0,
}

_APPROX_DEFAULT = 7.0


@dataclass
class BundleOption:
    name: str
    path: Path
    bundle: ModelBundle
    fits: bool
    reason: str


@dataclass
class OllamaStatus:
    installed: bool
    running: bool
    models: list[str]
    install_hint: str


OLLAMA_INSTALL_HINTS = {
    "Linux": "curl -fsSL https://ollama.com/install.sh | sh",
    "Darwin": "brew install ollama   (or download from https://ollama.com/download/mac)",
    "Windows": "winget install Ollama.Ollama   (or https://ollama.com/download/windows)",
}


def list_available_bundles(bundles_dir: Path) -> list[BundleOption]:
    options: list[BundleOption] = []
    if not bundles_dir.is_dir():
        return options
    for path in sorted(bundles_dir.glob("*.yaml")):
        try:
            data = path.read_text(encoding="utf-8")
            import yaml

            bundle = ModelBundle.model_validate(yaml.safe_load(data))
        except Exception:
            continue
        options.append(BundleOption(name=bundle.name, path=path, bundle=bundle, fits=False, reason=""))
    return options


def _estimate_download_gb(model_id: str) -> float:
    if model_id in _APPROX_DOWNLOAD_GB:
        return _APPROX_DOWNLOAD_GB[model_id]
    for key, value in _APPROX_DOWNLOAD_GB.items():
        if key.split(":")[0] in model_id:
            return value
    return _APPROX_DEFAULT


def explain_bundle(bundle: ModelBundle, report: HardwareReport) -> str:
    lines: list[str] = []
    if bundle.description:
        lines.append(bundle.description)
    lines.append(
        f"Memory floor: {bundle.minimum_ram_gb} GB RAM"
        + (f", {bundle.minimum_vram_gb} GB VRAM" if bundle.minimum_vram_gb else "")
        + (", sequential loading" if bundle.sequential_loading else ", concurrent loading")
    )
    downloads = []
    total = 0.0
    for spec in bundle.models:
        size = _estimate_download_gb(spec.model)
        total += size
        tool_label = "tool-capable" if spec.tool_capable else "reasoner/review only"
        downloads.append(f"  • {spec.model} ({spec.role}, {tool_label}, ~{size:.1f} GB)")
    lines.append(f"Estimated downloads: ~{total:.1f} GB total")
    lines.extend(downloads)
    lines.append(f"Your host: {report.ram_gb} GB RAM, {report.vram_gb or 0} GB VRAM, "
                 f"{report.disk_free_gb} GB disk free")
    return "\n".join(lines)


def classify_bundle_fit(bundle: ModelBundle, report: HardwareReport) -> tuple[bool, str]:
    if bundle.minimum_ram_gb and report.ram_gb < bundle.minimum_ram_gb:
        return False, f"Needs {bundle.minimum_ram_gb} GB RAM; you have {report.ram_gb} GB."
    if bundle.minimum_vram_gb and report.vram_gb < bundle.minimum_vram_gb:
        if not (report.metal and report.unified_memory):
            return False, f"Needs {bundle.minimum_vram_gb} GB VRAM; you have {report.vram_gb} GB."
    if bundle.models:
        total_download = sum(_estimate_download_gb(s.model) for s in bundle.models)
        if total_download > report.disk_free_gb:
            return False, f"Needs ~{total_download:.0f} GB disk; you have {report.disk_free_gb} GB free."
    return True, "Fits your hardware."


def pick_default_bundle(options: list[BundleOption], report: HardwareReport) -> BundleOption | None:
    target = recommended_profile(report)
    for opt in options:
        if opt.name == target:
            fits, reason = classify_bundle_fit(opt.bundle, report)
            opt.fits = fits
            opt.reason = reason
            return opt
    return None


def check_ollama(base_url: str = "http://127.0.0.1:11434") -> OllamaStatus:
    installed = shutil.which("ollama") is not None
    import platform as _platform

    hint = OLLAMA_INSTALL_HINTS.get(_platform.system(), "See https://ollama.com/download")
    if not installed:
        return OllamaStatus(installed=False, running=False, models=[], install_hint=hint)
    try:
        response = httpx.get(f"{base_url.rstrip('/')}/api/tags", timeout=3.0)
        response.raise_for_status()
        data = response.json()
        models = [m.get("name", "") for m in data.get("models", [])]
        return OllamaStatus(installed=True, running=True, models=models, install_hint=hint)
    except (httpx.HTTPError, ValueError):
        return OllamaStatus(installed=True, running=False, models=[], install_hint=hint)
