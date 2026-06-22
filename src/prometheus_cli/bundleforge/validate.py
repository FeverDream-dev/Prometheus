from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..hardware import HardwareReport
from .catalog import ModelCatalog, load_catalog
from .recommend import list_templates, load_template
from .schema import ForgeBundle, load_forge_bundle

_UNSAFE_MODEL_RE = re.compile(r"\.\.|/\.\./|\\|\s|;|`|\$|\(")
_VALID_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]*$")


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    bundle: ForgeBundle | None = None

    @property
    def passed(self) -> bool:
        return self.valid and len(self.errors) == 0


def _check_model_id(model_id: str) -> list[str]:
    errors: list[str] = []
    if _UNSAFE_MODEL_RE.search(model_id):
        errors.append(f"Unsafe characters in model id: {model_id!r}")
    if not _VALID_MODEL_RE.match(model_id):
        errors.append(f"Invalid model id format: {model_id!r}")
    return errors


def validate_bundle(
    bundle: ForgeBundle,
    catalog: ModelCatalog | None = None,
    hardware: HardwareReport | None = None,
) -> ValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    cat = catalog or load_catalog()

    for role_name, spec in bundle.roles.items():
        errors.extend(_check_model_id(spec.model))

    for opt_name, model_id in bundle.optional.items():
        errors.extend(_check_model_id(model_id))

    if not bundle.roles:
        errors.append("Bundle must define at least one role")

    for model_id in bundle.all_model_ids:
        entry = cat.by_id(model_id)
        if entry is None:
            warnings.append(f"Model '{model_id}' not found in catalog — license/size unverified")
        else:
            if not entry.commercial_safe and bundle.commercial_safe:
                errors.append(
                    f"Bundle claims commercial_safe=True but model '{model_id}' "
                    f"has license '{entry.license}' (non-commercial)"
                )
            if hardware is not None:
                if entry.min_ram_gb > hardware.ram_gb:
                    warnings.append(
                        f"Model '{model_id}' needs {entry.min_ram_gb} GB RAM; host has {hardware.ram_gb:.0f} GB"
                    )
                if entry.min_vram_gb > hardware.vram_gb:
                    warnings.append(
                        f"Model '{model_id}' needs {entry.min_vram_gb} GB VRAM; host has {hardware.vram_gb:.0f} GB"
                    )

    if hardware is not None:
        if bundle.requirements.min_ram_gb > hardware.ram_gb:
            errors.append(
                f"Bundle requires {bundle.requirements.min_ram_gb} GB RAM; host has {hardware.ram_gb:.0f} GB"
            )
        if bundle.requirements.min_vram_gb > hardware.vram_gb:
            errors.append(
                f"Bundle requires {bundle.requirements.min_vram_gb} GB VRAM; host has {hardware.vram_gb:.0f} GB"
            )

    if not bundle.license_notes:
        warnings.append("No license_notes provided — users won't know license implications")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        bundle=bundle,
    )


def validate_template(
    template_id: str,
    catalog: ModelCatalog | None = None,
    hardware: HardwareReport | None = None,
) -> ValidationResult:
    try:
        bundle = load_template(template_id)
    except FileNotFoundError:
        return ValidationResult(
            valid=False,
            errors=[f"Template '{template_id}' not found. Available: {', '.join(list_templates())}"],
        )
    return validate_bundle(bundle, catalog=catalog, hardware=hardware)


def validate_all_templates(
    catalog: ModelCatalog | None = None,
    hardware: HardwareReport | None = None,
) -> dict[str, ValidationResult]:
    results: dict[str, ValidationResult] = {}
    for template_id in list_templates():
        results[template_id] = validate_template(template_id, catalog=catalog, hardware=hardware)
    return results


def validate_file(
    path: Path,
    catalog: ModelCatalog | None = None,
    hardware: HardwareReport | None = None,
) -> ValidationResult:
    try:
        bundle = load_forge_bundle(Path(path))
    except Exception as exc:
        return ValidationResult(valid=False, errors=[f"Failed to parse bundle YAML: {exc}"])
    return validate_bundle(bundle, catalog=catalog, hardware=hardware)


__all__ = [
    "ValidationResult",
    "validate_all_templates",
    "validate_bundle",
    "validate_file",
    "validate_template",
]
