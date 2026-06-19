from __future__ import annotations

import pytest

from prometheus_cli.bundles import (
    BundleHardware,
    BundleLicense,
    BundleQualification,
    BundleRuntime,
    BundleV2,
    RoleSpecV2,
    load_registry,
)
from prometheus_cli.router import (
    MemSnapshot,
    ModelRouter,
    RoutingError,
    estimate_runtime_memory_gb,
    kv_cache_gb,
    plan_fallback,
)


def _mem(free_ram=32.0, free_vram=0.0, total=64.0):
    return MemSnapshot(total_ram_gb=total, free_ram_gb=free_ram, free_vram_gb=free_vram)


def _forge():
    return next(b for b in load_registry() if b.id == "forge-12gb")


def _vt():
    return next(b for b in load_registry() if b.id == "vibethinker-review-addon")


def _concurrent_bundle(max_loaded: int = 2) -> BundleV2:
    return BundleV2(
        id="test-concurrent",
        name="Test Concurrent",
        description="synthetic bundle allowing concurrent residency",
        hardware=BundleHardware(minimum_ram_gb=8, minimum_free_disk_gb=1),
        runtime=BundleRuntime(
            provider="ollama", sequential_loading=False,
            maximum_loaded_models=max_loaded, default_context=8192,
        ),
        roles={
            "controller": RoleSpecV2(
                model="alpha:7b", approximate_download_gb=4.5,
                capabilities=["text", "tools", "image"], keep_alive="5m",
            ),
            "reviewer": RoleSpecV2(
                model="beta:3b", approximate_download_gb=2.0,
                capabilities=["text", "tools"], keep_alive="5m",
            ),
        },
        licenses=[
            BundleLicense(model="alpha:7b", license="Apache-2.0", source="https://example/alpha"),
            BundleLicense(model="beta:3b", license="MIT", source="https://example/beta"),
        ],
        qualification=BundleQualification(required=["chat"]),
    )


def test_router_rejects_add_on_bundle():
    with pytest.raises(RoutingError):
        ModelRouter(_vt(), mem_probe=lambda: _mem())


def test_router_selects_controller_with_tools_capability():
    router = ModelRouter(_forge(), mem_probe=lambda: _mem(free_ram=64))
    decision = router.select("controller", required_capability="tools")
    assert decision.spec.model == "qwen3.5:9b"
    assert decision.will_load
    assert any("fits" in r or "Concurrent" in r for r in decision.reasons)


def test_router_refuses_prohibited_tools_role():
    bundle = _concurrent_bundle()
    bundle.roles["reviewer"] = RoleSpecV2(
        model="gamma:3b", approximate_download_gb=1.5,
        capabilities=["text", "tools"], prohibited_capabilities=["tools"], keep_alive="5m",
    )
    bundle.licenses.append(BundleLicense(model="gamma:3b", license="MIT", source="https://example/gamma"))
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=64))
    with pytest.raises(RoutingError, match="prohibited"):
        router.select("reviewer", required_capability="tools")


def test_router_refuses_vision_task_for_text_only_role():
    router = ModelRouter(_forge(), mem_probe=lambda: _mem())
    with pytest.raises(RoutingError, match="vision"):
        router.select("reviewer", required_capability="image")


def test_concurrent_load_when_memory_available():
    bundle = _concurrent_bundle(max_loaded=2)
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=64))
    loaded = {"controller": (bundle.roles["controller"], 8192)}
    decision = router.select("reviewer", currently_loaded=loaded)
    assert decision.sequential_swap is False
    assert any(a.action == "load" for a in decision.actions)


def test_sequential_hot_swap_when_memory_constrained():
    bundle = _concurrent_bundle(max_loaded=2)
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=2.0))
    loaded = {"controller": (bundle.roles["controller"], 8192)}
    decision = router.select("reviewer", currently_loaded=loaded)
    assert decision.sequential_swap is True
    assert any(a.action == "unload" for a in decision.actions)
    assert any(a.action == "load" for a in decision.actions)


def test_real_bundles_are_sequential_by_design():
    for b in load_registry():
        if b.is_add_on:
            continue
        assert b.runtime.maximum_loaded_models == 1, f"{b.id} allows concurrent residency"


def test_sequential_swap_required_when_maximum_loaded_models_is_one():
    bundle = _forge()
    assert bundle.runtime.maximum_loaded_models == 1
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=128))
    loaded = {"controller": (bundle.roles["controller"], 8192)}
    decision = router.select("reviewer", currently_loaded=loaded)
    assert decision.sequential_swap is True
    assert any(a.action == "unload" for a in decision.actions)


def test_handoff_preserved_across_swap():
    bundle = _forge()
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=4.0))
    decision = router.select(
        "reviewer",
        currently_loaded={"controller": (bundle.roles["controller"], 8192)},
        handoff={"task": "fix-calculator", "diff": "calculator.py"},
    )
    assert decision.handoff == {"task": "fix-calculator", "diff": "calculator.py"}


def test_already_loaded_role_keeps_resident():
    bundle = _forge()
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=64))
    loaded = {"controller": (bundle.roles["controller"], 8192)}
    decision = router.select("controller", currently_loaded=loaded)
    assert decision.actions[0].action == "keep"
    assert not decision.will_load


def test_low_memory_reduces_context():
    bundle = _forge()
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=0.1))
    decision = router.select("controller")
    assert any("Reduced context" in r for r in decision.reasons)


def test_kv_cache_scales_with_context_and_model():
    small = kv_cache_gb(8192, 4.5)
    large = kv_cache_gb(32768, 17.0)
    assert small > 0
    assert large > small


def test_estimate_runtime_memory_includes_weights_overhead_kv():
    bundle = _forge()
    est = estimate_runtime_memory_gb(bundle.roles["controller"], 16384)
    assert est > bundle.roles["controller"].approximate_download_gb


def test_plan_fallback_lists_alternative_tool_capable_roles():
    bundle = _forge()
    fallback = plan_fallback(bundle, "controller", mem_probe=lambda: _mem())
    assert isinstance(fallback, list)
    assert all(":" in c for c in fallback)


def test_every_reason_is_human_readable():
    bundle = _forge()
    router = ModelRouter(bundle, mem_probe=lambda: _mem(free_ram=64))
    decision = router.select("controller")
    assert decision.reasons
    assert all(isinstance(r, str) and len(r) > 3 for r in decision.reasons)
