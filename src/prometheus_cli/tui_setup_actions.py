"""Bundle setup actions for the interactive TUI wizard.

Activates a package, pulls missing Ollama models, and runs qualification /
inference smoke tests. Shared by the CLI ``models pull`` path and the TUI.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

StatusFn = Callable[[str], None]


def _noop_status(_line: str) -> None:
    pass


def activate_bundle(bundle_id: str, *, home: Path | None = None) -> tuple[bool, str]:
    """Write active bundle YAML and update settings. Returns (ok, message)."""
    import yaml

    from .bundles import find_bundle, load_registry
    from .config import ensure_home, load_settings, save_settings

    match = find_bundle(bundle_id, load_registry())
    if match is None:
        return False, f"No package '{bundle_id}'."
    if match.is_add_on:
        return False, f"'{bundle_id}' is an add-on; cannot be active."

    root = home or ensure_home()
    active_dir = root / "bundles"
    active_dir.mkdir(parents=True, exist_ok=True)
    active_path = active_dir / f"active-{match.id}.yaml"
    active_path.write_text(
        yaml.safe_dump(match.to_v1_bundle().model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    settings = load_settings()
    settings.active_bundle_id = match.id
    settings.bundle_file = active_path
    save_settings(settings)
    return True, f"Active package: {match.name} ({match.id})"


def pull_bundle_models(
    bundle_id: str,
    *,
    base_url: str = "http://127.0.0.1:11434",
    verify: bool = True,
    yes: bool = False,
    confirm_large: Callable[[str], bool] | None = None,
    on_status: StatusFn | None = None,
) -> bool:
    """Pull every role model for ``bundle_id``. Returns True when all required pulls succeed."""
    from .bundles import find_bundle, load_registry
    from .model_aliases import resolve_alias
    from .onboarding import (
        check_ollama,
        format_pull_progress,
        inference_smoke_test,
        pull_model,
        start_ollama_service,
    )
    from .pull_policy import confirm_large_pull, requires_pull_confirmation

    emit = on_status or _noop_status

    status = check_ollama(base_url)
    if not status.running:
        emit("Starting Ollama service…")
        if not start_ollama_service(base_url):
            emit(f"Ollama not responding at {base_url}. Run: ollama serve")
            return False
        status = check_ollama(base_url)

    match = find_bundle(bundle_id, load_registry())
    if match is None:
        emit(f"No package '{bundle_id}'.")
        return False

    targets = [resolve_alias(r.model) for r in match.roles.values()]
    to_pull = [t for t in targets if t not in status.models]
    if to_pull:
        needs, size, largest = requires_pull_confirmation(to_pull)
        if needs:
            emit(f"Large download: {largest} (~{size:.1f} GB)")
        if not confirm_large_pull(
            to_pull,
            yes=yes,
            confirm_fn=(lambda _p, _d: confirm_large(_p)) if confirm_large else None,
        ):
            emit("Pull cancelled.")
            return False

    ok_all = True
    for tag in targets:
        if tag in status.models:
            emit(f"Already installed: {tag}")
            continue
        emit(f"Pulling {tag}…")
        last: dict[str, Any] = {"pct": -1}

        def on_progress(data: dict, _last: dict = last) -> None:
            line = format_pull_progress(data)
            pct = data.get("completed", 0) * 100 // max(data.get("total", 1), 1)
            if pct != _last["pct"] or data.get("status") in ("success", "pulling manifest"):
                emit(f"  {line}")
                _last["pct"] = pct

        if pull_model(tag, base_url=base_url, on_progress=on_progress):
            emit(f"Pulled {tag}.")
        else:
            emit(f"Pull failed for {tag}. Try: ollama pull {tag}")
            ok_all = False
            continue
        if verify:
            smoke = inference_smoke_test(tag, base_url=base_url)
            if smoke.success:
                emit(f"Inference OK on {tag}: {smoke.response[:60]}")
            else:
                emit(f"Inference probe: {smoke.error or 'no response'} (model may still work)")
    return ok_all


def verify_bundle_setup(
    bundle_id: str,
    *,
    on_status: StatusFn | None = None,
) -> bool:
    """Run bundle qualification checks. Returns True when the report passes."""
    from .bundles import load_registry
    from .onboarding import check_ollama
    from .qualification import qualify_bundle

    emit = on_status or _noop_status
    if not check_ollama().running:
        emit("Ollama service is not running.")
        return False
    target = next((b for b in load_registry() if b.id == bundle_id), None)
    if target is None:
        emit(f"No bundle '{bundle_id}'.")
        return False
    emit(f"Qualifying {target.id}…")
    report = qualify_bundle(target)
    for r in report.results:
        mark = "PASS" if r.passed else "FAIL"
        emit(f"  {mark} {r.name} — {r.detail}")
    verdict = "QUALIFIED" if report.passed else "PARTIAL"
    emit(f"{verdict}: {report.passed_count}/{len(report.results)}")
    return report.passed


def setup_bundle_end_to_end(
    bundle_id: str,
    *,
    pull: bool = True,
    verify: bool = True,
    yes: bool = False,
    confirm_large: Callable[[str], bool] | None = None,
    on_status: StatusFn | None = None,
) -> bool:
    """Activate, optionally pull models, then qualify. One-shot setup from the TUI."""
    emit = on_status or _noop_status
    ok, msg = activate_bundle(bundle_id)
    emit(msg)
    if not ok:
        return False
    if pull:
        if not pull_bundle_models(
            bundle_id,
            verify=verify,
            yes=yes,
            confirm_large=confirm_large,
            on_status=emit,
        ):
            return False
    if verify:
        return verify_bundle_setup(bundle_id, on_status=emit)
    return True


__all__ = [
    "activate_bundle",
    "pull_bundle_models",
    "setup_bundle_end_to_end",
    "verify_bundle_setup",
]
