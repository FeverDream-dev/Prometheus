from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .hardware import HardwareReport
from .models import ModelBundle, ModelSpec

SCHEMA_VERSION = 2

_REPO_BUILT_IN_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "bundles-v2"


def _resolve_built_in_dir() -> Path:
    from .resources import get_default_bundles_dir
    packaged = get_default_bundles_dir()
    if packaged.is_dir() and any(packaged.glob("*.yaml")):
        return packaged
    return _REPO_BUILT_IN_DIR


BUILT_IN_DIR = _resolve_built_in_dir()

KNOWN_ROLES = ("controller", "coder", "planner", "reasoner", "reviewer", "vision", "embedding", "guardian")
KNOWN_CAPABILITIES = ("text", "image", "tools", "thinking", "coding", "json", "embeddings", "structured_output")
QUALIFICATION_TESTS = (
    "chat", "image", "image_description", "screenshot_ocr", "screenshot_error_detection",
    "structured_output", "single_tool", "parallel_tool", "multi_turn_tool", "code_patch",
    "patch_review", "repository_navigation", "test_repair", "reasoning", "failure_diagnosis",
    "long_session", "specialist_handoff", "no_tool_call_enforcement",
)

_MODEL_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@-]*$")
_UNSAFE_PATH_RE = re.compile(r"\.\.|/\.\./|\\|\s")


class BundleHardware(BaseModel):
    model_config = ConfigDict(extra="forbid")
    minimum_ram_gb: int = Field(ge=0)
    recommended_ram_gb: int | None = None
    minimum_vram_gb: int = Field(default=0, ge=0)
    recommended_vram_gb: int | None = None
    minimum_free_disk_gb: int = Field(default=0, ge=0)
    acceleration: str | None = None
    platform: list[str] = Field(default_factory=list)


class BundleRuntime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "ollama"
    minimum_version: str | None = None
    sequential_loading: bool = True
    maximum_loaded_models: int = Field(default=1, ge=1)
    default_context: int = Field(default=8192, ge=512)
    context_ceiling: int | None = None
    unlimited_local_sessions: bool = True


class RoleSpecV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    approximate_download_gb: float = Field(ge=0)
    capabilities: list[str] = Field(default_factory=list)
    prohibited_capabilities: list[str] = Field(default_factory=list)
    keep_alive: str | int = "5m"
    optional: bool = False
    quantization: str | None = None

    @field_validator("model")
    @classmethod
    def _safe_model_id(cls, v: str) -> str:
        if _UNSAFE_PATH_RE.search(v) or not _MODEL_ID_RE.match(v):
            raise ValueError(f"unsafe or invalid model id: {v!r}")
        return v


class BundleLicense(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model: str
    license: str
    source: str

    @field_validator("source")
    @classmethod
    def _https_source(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError(f"license source must be an https URL: {v!r}")
        return v


class BundleQualification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: list[str] = Field(default_factory=list)
    vision_required_when_installed: list[str] | None = None
    last_qualified_version: str | None = None
    last_qualified_date: str | None = None

    @field_validator("required")
    @classmethod
    def _known_tests(cls, v: list[str]) -> list[str]:
        unknown = [t for t in v if t not in QUALIFICATION_TESTS]
        if unknown:
            raise ValueError(f"unknown qualification tests: {unknown}")
        return v


class BundleV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[2] = 2
    id: str
    name: str
    description: str = ""
    recommended_for: list[str] = Field(default_factory=list)
    hardware: BundleHardware
    runtime: BundleRuntime
    roles: dict[str, RoleSpecV2]
    licenses: list[BundleLicense] = Field(min_length=1)
    qualification: BundleQualification = Field(default_factory=BundleQualification)
    experimental: bool = False
    upgrade: str | None = None

    @field_validator("id")
    @classmethod
    def _id_shape(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]+$", v):
            raise ValueError(f"invalid bundle id: {v!r}")
        return v

    @field_validator("roles")
    @classmethod
    def _known_roles(cls, v: dict) -> dict:
        unknown = [r for r in v if r not in KNOWN_ROLES]
        if unknown:
            raise ValueError(f"unknown roles: {unknown}")
        if "controller" not in v and not {r for r in v if r in ("reviewer", "reasoner")}:
            raise ValueError("bundle must define a 'controller' role or a review/reasoner add-on role")
        return v

    def _licensed_models(self) -> set[str]:
        return {lic.model for lic in self.licenses}

    def _role_models(self) -> set[str]:
        return {role.model for role in self.roles.values()}

    @field_validator("licenses")
    @classmethod
    def _every_role_licensed(cls, v: list[BundleLicense]) -> list[BundleLicense]:
        return v

    def model_post_init(self, __context) -> None:
        licensed = self._licensed_models()
        missing = []
        for role_model in self._role_models():
            if not any(lm == role_model or lm in role_model or role_model in lm for lm in licensed):
                missing.append(role_model)
        if missing:
            raise ValueError(f"missing license info for models: {sorted(missing)}")
        controller = self.roles.get("controller")
        if controller and controller.keep_alive == 0 and "tools" in controller.capabilities:
            if self.runtime.maximum_loaded_models > 1 and not self.runtime.sequential_loading:
                raise ValueError("tool-capable controller with keep_alive 0 cannot be concurrent")

    def for_role(self, role: str, base_url: str | None = None) -> ModelSpec:
        if role in self.roles:
            spec = self.roles[role]
        elif role in {"coder", "reasoner", "reviewer"} and "controller" in self.roles:
            spec = self.roles["controller"]
        else:
            raise KeyError(f"No role '{role}' in bundle {self.id}")
        tool_capable = "tools" in spec.capabilities and "tools" not in spec.prohibited_capabilities
        return ModelSpec(
            provider=self.runtime.provider,
            model=spec.model,
            role=role if role in self.roles else "controller",
            base_url=base_url,
            context_window=self.runtime.default_context,
            keep_alive=spec.keep_alive,
            tool_capable=tool_capable,
        )

    def controller_spec(self, base_url: str | None = None) -> ModelSpec:
        if "controller" not in self.roles:
            raise ValueError(f"bundle '{self.id}' is an add-on (no controller) and cannot drive the agent loop")
        return self.for_role("controller", base_url=base_url)

    @property
    def is_add_on(self) -> bool:
        return "controller" not in self.roles

    def to_v1_bundle(self, base_url: str | None = None) -> ModelBundle:
        v1_roles = ("controller", "coder", "reasoner", "reviewer", "vision")
        specs = [self.for_role(role, base_url=base_url) for role in self.roles if role in v1_roles]
        if not any(s.role == "controller" for s in specs) and not self.is_add_on:
            specs.insert(0, self.controller_spec(base_url=base_url))
        return ModelBundle(
            name=self.id,
            description=self.description,
            minimum_ram_gb=self.hardware.minimum_ram_gb,
            minimum_vram_gb=self.hardware.minimum_vram_gb,
            sequential_loading=self.runtime.sequential_loading,
            models=specs,
        )

    def total_download_gb(self) -> float:
        return sum(r.approximate_download_gb for r in self.roles.values())

    def installed_fraction(self, installed_models: list[str]) -> float:
        if not self.roles:
            return 0.0
        present = sum(1 for r in self.roles.values() if r.model in installed_models)
        return present / len(self.roles)


BundleStatus = Literal["recommended", "installed", "available", "experimental", "incompatible"]


class ClassifiedBundle(BaseModel):
    bundle: BundleV2
    status: BundleStatus
    fits_hardware: bool
    reasons: list[str] = Field(default_factory=list)

    @property
    def id(self) -> str:
        return self.bundle.id


def load_bundle(path: Path) -> BundleV2:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return BundleV2.model_validate(data)


def load_registry(directory: Path | None = None) -> list[BundleV2]:
    if directory is None:
        directory = _resolve_built_in_dir()
    base = Path(directory)
    if not base.is_dir():
        return []
    out: list[BundleV2] = []
    for path in sorted(base.glob("*.yaml")):
        out.append(load_bundle(path))
    return out


def hardware_fits(bundle: BundleV2, report: HardwareReport) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    ok = True
    hw = bundle.hardware
    if report.ram_gb < hw.minimum_ram_gb:
        ok = False
        reasons.append(f"needs {hw.minimum_ram_gb} GB RAM; you have {report.ram_gb:.0f} GB")
    if hw.minimum_vram_gb and report.vram_gb < hw.minimum_vram_gb:
        if not (report.metal and report.unified_memory):
            ok = False
            reasons.append(f"needs {hw.minimum_vram_gb} GB VRAM; you have {report.vram_gb:.0f} GB")
    total_download = bundle.total_download_gb()
    if total_download > report.disk_free_gb:
        ok = False
        reasons.append(f"needs ~{total_download:.0f} GB disk; you have {report.disk_free_gb:.0f} GB free")
    if ok and not reasons:
        reasons.append(
            f"Fits {report.ram_gb:.0f} GB RAM, {report.vram_gb:.0f} GB VRAM, "
            f"{report.disk_free_gb:.0f} GB disk"
        )
    return ok, reasons


def classify_bundle(
    bundle: BundleV2,
    report: HardwareReport,
    installed_models: list[str] | None = None,
    recommended_id: str | None = None,
) -> ClassifiedBundle:
    installed_models = installed_models or []
    fits, fit_reasons = hardware_fits(bundle, report)
    reasons = list(fit_reasons)
    frac = bundle.installed_fraction(installed_models)
    if frac >= 1.0 and fits:
        reasons.append("All roles already installed locally")
        return ClassifiedBundle(bundle=bundle, status="installed", fits_hardware=True, reasons=reasons)
    if frac > 0:
        reasons.append(f"{frac*100:.0f}% of roles already installed")
    if bundle.experimental:
        reasons.append("Experimental package")
        return ClassifiedBundle(bundle=bundle, status="experimental", fits_hardware=fits, reasons=reasons)
    if not fits:
        return ClassifiedBundle(bundle=bundle, status="incompatible", fits_hardware=False, reasons=reasons)
    if recommended_id and bundle.id == recommended_id:
        reasons.insert(0, "Best fit for your detected hardware")
        return ClassifiedBundle(bundle=bundle, status="recommended", fits_hardware=True, reasons=reasons)
    return ClassifiedBundle(bundle=bundle, status="available", fits_hardware=True, reasons=reasons)


def classify_registry(
    bundles: list[BundleV2],
    report: HardwareReport,
    installed_models: list[str] | None = None,
) -> list[ClassifiedBundle]:
    installed_models = installed_models or []
    recommended = _pick_recommended(bundles, report)
    return [
        classify_bundle(b, report, installed_models, recommended_id=recommended)
        for b in bundles
    ]


def _pick_recommended(bundles: list[BundleV2], report: HardwareReport) -> str | None:
    candidates = []
    for b in bundles:
        if b.experimental or b.is_add_on:
            continue
        fits, _ = hardware_fits(b, report)
        if fits:
            candidates.append(b)
    if not candidates:
        return None
    if report.vram_gb >= 22:
        preference = {"titan-24gb": 0, "hephaestus-code-24gb": 1, "forge-12gb": 2, "oracle-gemma4-12gb": 3}
    elif report.vram_gb >= 10 or (report.metal and report.ram_gb >= 16):
        preference = {"forge-12gb": 0, "oracle-gemma4-12gb": 1, "ember-8gb-gpu": 2}
    elif report.vram_gb >= 6:
        preference = {"ember-8gb-gpu": 0, "forge-12gb": 1}
    else:
        preference = {"spark-cpu-8gb": 0, "ember-8gb-gpu": 1}
    ranked = sorted(candidates, key=lambda b: preference.get(b.id, 99))
    return ranked[0].id


_SECRET_KEY_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password|credential)")
_ABS_PATH_RE = re.compile(r"^/|[A-Za-z]:[\\/]|^\.\./")


def sanitize_bundle(bundle: BundleV2) -> dict:
    """Return a dict representation safe to export/share: strips any field whose
    name looks like a secret, drops values containing absolute/personal paths,
    and never includes API keys. Built-in v2 manifests have none of these, but
    custom/user bundles must be sanitized before export."""
    data = bundle.model_dump(mode="json")
    return _strip_unsafe(data)


def _strip_unsafe(node):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if _SECRET_KEY_RE.search(str(k)):
                continue
            out[k] = _strip_unsafe(v)
        return out
    if isinstance(node, list):
        return [_strip_unsafe(item) for item in node]
    if isinstance(node, str):
        if _ABS_PATH_RE.search(node) and "://" not in node:
            return None
        return node
    return node


def find_bundle(bundle_id: str, registry: list[BundleV2] | None = None) -> BundleV2 | None:
    registry = registry if registry is not None else load_registry()
    return next((b for b in registry if b.id == bundle_id), None)

__all__ = [
    "BUILT_IN_DIR",
    "BundleHardware",
    "BundleLicense",
    "BundleQualification",
    "BundleRuntime",
    "BundleV2",
    "ClassifiedBundle",
    "RoleSpecV2",
    "classify_bundle",
    "classify_registry",
    "find_bundle",
    "hardware_fits",
    "load_bundle",
    "load_registry",
    "sanitize_bundle",
]
