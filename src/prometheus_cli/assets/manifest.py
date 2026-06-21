from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KNOWN_LICENSES: dict[str, dict[str, str]] = {
    "stabilityai/sdxl-turbo": {"license": "STABILITY-AI", "commercial": "restricted", "source": "https://huggingface.co/stabilityai/sdxl-turbo"},
    "black-forest-labs/FLUX.1-schnell": {"license": "Apache-2.0", "commercial": "allowed", "source": "https://huggingface.co/black-forest-labs/FLUX.1-schnell"},
    "rembg/u2netp": {"license": "MIT", "commercial": "allowed", "source": "https://github.com/danielgatis/rembg"},
    "rembg/silueta": {"license": "MIT", "commercial": "allowed", "source": "https://github.com/danielgatis/rembg"},
    "briaai/RMBG-1.4": {"license": "non-commercial", "commercial": "restricted", "source": "https://huggingface.co/briaai/RMBG-1.4"},
}

VALID_KINDS = ("icon", "hero", "illustration", "logo", "dashboard", "mockup", "background")
VALID_SIZES = ("256x256", "512x512", "1024x1024", "1536x864", "1920x1080")


@dataclass
class AssetManifest:
    name: str
    kind: str
    model: str = ""
    prompt: str = ""
    negative_prompt: str = ""
    seed: int = 0
    size: str = "512x512"
    steps: int = 4
    transparent: bool = False
    background_removal_model: str = ""
    commercial_use: str = "unknown"
    license_id: str = ""
    license_url: str = ""
    post_processing: list[str] = field(default_factory=list)
    generated_at: str = ""
    files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()
        if self.model:
            lic = KNOWN_LICENSES.get(self.model, {})
            if lic:
                self.license_id = lic.get("license", "")
                self.license_url = lic.get("source", "")
                if self.commercial_use == "unknown":
                    self.commercial_use = lic.get("commercial", "unknown")
        if self.model.startswith("stabilityai/") and self.commercial_use == "allowed":
            self.warnings.append("Stability AI models have a restricted license; verify commercial terms before use.")
        if self.background_removal_model and "bria" in self.background_removal_model.lower() and self.commercial_use == "allowed":
            self.warnings.append("BRIA RMBG is non-commercial unless separately licensed; cannot be used for commercial output by default.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AssetManifest":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


def write_manifest(asset_dir: Path, manifest: AssetManifest) -> tuple[Path, Path]:
    asset_dir.mkdir(parents=True, exist_ok=True)
    mp = asset_dir / "manifest.json"
    mp.write_text(manifest.to_json(), encoding="utf-8")
    readme_lines = [
        f"# {manifest.name}",
        "",
        f"- Kind: {manifest.kind}",
        f"- Model: `{manifest.model}`",
        f"- License: {manifest.license_id or 'unknown'}",
        f"- Commercial use: **{manifest.commercial_use}**",
        f"- Seed: {manifest.seed}",
        f"- Size: {manifest.size}",
        f"- Transparent: {manifest.transparent}",
        f"- Created: {manifest.generated_at}",
        "",
    ]
    if manifest.prompt:
        readme_lines.append(f"Prompt: {manifest.prompt}")
    if manifest.warnings:
        readme_lines.append("")
        readme_lines.append("## Warnings")
        for w in manifest.warnings:
            readme_lines.append(f"- {w}")
    rp = asset_dir / "README.md"
    rp.write_text("\n".join(readme_lines) + "\n", encoding="utf-8")
    return mp, rp


def can_use_commercially(model: str) -> bool:
    lic = KNOWN_LICENSES.get(model, {})
    return lic.get("commercial") == "allowed"


__all__ = [
    "AssetManifest",
    "KNOWN_LICENSES",
    "VALID_KINDS",
    "VALID_SIZES",
    "can_use_commercially",
    "write_manifest",
]
