from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .bundles import BundleV2, RoleSpecV2
from .models import ModelSpec

_BYTES_PER_GB = 1024**3


@dataclass
class MemSnapshot:
    total_ram_gb: float
    free_ram_gb: float
    free_vram_gb: float
    source: str = "probe"


def _meminfo_available_gb() -> float | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    for key in ("MemAvailable", "MemFree"):
        m = re.search(rf"^{key}:\s+(\d+)\s+kB", text, re.MULTILINE)
        if m:
            return int(m.group(1)) * 1024 / _BYTES_PER_GB
    return None


def _meminfo_total_gb() -> float | None:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
    except OSError:
        return None
    m = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.MULTILINE)
    return int(m.group(1)) * 1024 / _BYTES_PER_GB if m else None


def probe_memory(hardware_report=None) -> MemSnapshot:
    from .hardware import detect_hardware

    report = hardware_report or detect_hardware()
    free = _meminfo_available_gb()
    if free is None:
        free = report.ram_gb * 0.5
    total = _meminfo_total_gb() or report.ram_gb
    return MemSnapshot(
        total_ram_gb=total,
        free_ram_gb=max(0.0, free),
        free_vram_gb=max(0.0, report.vram_gb),
        source="/proc/meminfo" if _meminfo_available_gb() is not None else "estimate",
    )


def kv_cache_gb(context_tokens: int, weights_gb: float) -> float:
    # Heuristic, documented: a ~7B/Q4 model (~4.5 GB weights) uses roughly
    # 0.5 GB of KV cache per 8K context. Scale linearly with both. This is an
    # estimate for planning, not a guarantee; the runtime enforces a disk/RAM
    # safety floor separately.
    model_scale = max(weights_gb, 1.0) / 4.5
    per_8k = 0.5 * model_scale
    return per_8k * (context_tokens / 8192.0)


def estimate_runtime_memory_gb(role_spec: RoleSpecV2, context_tokens: int) -> float:
    weights = role_spec.approximate_download_gb
    overhead = weights * 0.1
    return weights + overhead + kv_cache_gb(context_tokens, weights)


@dataclass
class LoadAction:
    action: str  # "load" | "unload" | "keep"
    model: str
    role: str
    reason: str


@dataclass
class RouteDecision:
    role: str
    spec: RoleSpecV2
    model_spec: ModelSpec
    actions: list[LoadAction] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    handoff: dict = field(default_factory=dict)
    sequential_swap: bool = False

    @property
    def will_load(self) -> bool:
        return any(a.action == "load" for a in self.actions)


class RoutingError(RuntimeError):
    pass


class ModelRouter:
    def __init__(self, bundle: BundleV2, mem_probe=probe_memory, safety_floor_gb: float = 1.5):
        if bundle.is_add_on:
            raise RoutingError(f"bundle '{bundle.id}' is an add-on; it has no controller to route")
        self.bundle = bundle
        self._mem_probe = mem_probe
        self._safety_floor_gb = safety_floor_gb

    def _free_after(self, loaded: dict[str, tuple[RoleSpecV2, int]], context_tokens: int) -> float:
        mem = self._mem_probe()
        used = sum(estimate_runtime_memory_gb(spec, ctx) for spec, ctx in loaded.values())
        return max(0.0, mem.free_ram_gb - used)

    def select(
        self,
        role: str,
        required_capability: str | None = None,
        currently_loaded: dict[str, tuple[RoleSpecV2, int]] | None = None,
        context_tokens: int | None = None,
        handoff: dict | None = None,
    ) -> RouteDecision:
        currently_loaded = currently_loaded or {}
        spec = self._resolve_role(role)
        self._enforce_capability(role, spec, required_capability)
        ctx = context_tokens or self.bundle.runtime.default_context
        need = estimate_runtime_memory_gb(spec, ctx)
        actions: list[LoadAction] = []
        reasons: list[str] = []
        sequential = False

        if role in currently_loaded:
            actions.append(LoadAction("keep", spec.model, role, "already resident"))
            reasons.append(f"{spec.model} already loaded for {role}")
        else:
            free = self._free_after(currently_loaded, ctx)
            fits_concurrency = (
                len(currently_loaded) < self.bundle.runtime.maximum_loaded_models
                and free >= need + self._safety_floor_gb
            )
            if fits_concurrency:
                actions.append(LoadAction("load", spec.model, role, f"{need:.1f} GB fits in {free:.1f} GB free"))
                reasons.append(f"Concurrent load: {spec.model} (~{need:.1f} GB) fits alongside {len(currently_loaded)} resident")
            else:
                sequential = True
                victims = list(currently_loaded.items())
                freed = 0.0
                for victim_role, (victim_spec, victim_ctx) in victims:
                    if victim_role == role:
                        continue
                    freed += estimate_runtime_memory_gb(victim_spec, victim_ctx)
                    actions.append(LoadAction("unload", victim_spec.model, victim_role,
                                              "free memory for sequential hot-swap"))
                    if free + freed >= need + self._safety_floor_gb:
                        break
                if free + freed < need + self._safety_floor_gb:
                    reasons.append(
                        f"Insufficient memory even after unload (need {need:.1f} GB, "
                        f"would have {free + freed:.1f} GB); reducing context"
                    )
                    reduced_ctx = max(4096, ctx // 2)
                    need = estimate_runtime_memory_gb(spec, reduced_ctx)
                    reasons.append(f"Reduced context to {reduced_ctx} tokens (~{need:.1f} GB)")
                actions.append(LoadAction("load", spec.model, role, "sequential load after unload"))
                reasons.append(
                    f"Sequential hot-swap: unloading resident model(s) to load {spec.model} "
                    f"(maximum_loaded_models={self.bundle.runtime.maximum_loaded_models})"
                )

        return RouteDecision(
            role=role,
            spec=spec,
            model_spec=self.bundle.for_role(role),
            actions=actions,
            reasons=reasons,
            handoff=dict(handoff or {}),
            sequential_swap=sequential,
        )

    def _resolve_role(self, role: str) -> RoleSpecV2:
        if role in self.bundle.roles:
            return self.bundle.roles[role]
        if role in {"coder", "reasoner", "reviewer", "vision"} and "controller" in self.bundle.roles:
            return self.bundle.roles["controller"]
        raise RoutingError(f"No role '{role}' in bundle {self.bundle.id}")

    def _enforce_capability(self, role: str, spec: RoleSpecV2, required: str | None) -> None:
        if required == "tools":
            if "tools" in spec.prohibited_capabilities:
                raise RoutingError(f"{spec.model} is prohibited from tool use (prohibited_capabilities)")
            if "tools" not in spec.capabilities:
                raise RoutingError(f"{spec.model} lacks the 'tools' capability required for {role}")
        if required == "image" and "image" not in spec.capabilities:
            raise RoutingError(f"{spec.model} lacks vision ('image') capability; cannot route a vision task to it")


def plan_fallback(bundle: BundleV2, failed_role: str, mem_probe=probe_memory) -> list[str]:
    router = ModelRouter(bundle, mem_probe=mem_probe)
    candidates = []
    for role_name, spec in bundle.roles.items():
        if role_name == failed_role or spec.optional:
            continue
        try:
            router._enforce_capability(failed_role, spec, "tools")
            candidates.append(f"{role_name}:{spec.model}")
        except RoutingError:
            continue
    return candidates


__all__ = [
    "LoadAction",
    "MemSnapshot",
    "ModelRouter",
    "RouteDecision",
    "RoutingError",
    "estimate_runtime_memory_gb",
    "kv_cache_gb",
    "plan_fallback",
    "probe_memory",
]
