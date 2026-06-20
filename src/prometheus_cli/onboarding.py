"""Onboarding logic for `prometheus setup`.

Pure functions that decide which bundle fits the host are separated from the
interactive prompts so they can be unit-tested without a TTY. The setup command
never downloads a model without explicit confirmation, per PRODUCT_SPEC.
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
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
    hint = OLLAMA_INSTALL_HINTS.get(platform.system(), "See https://ollama.com/download")
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


@dataclass
class InstallPlan:
    command: str | None
    description: str
    needs_shell: bool


def ollama_install_plan(system: str | None = None) -> InstallPlan:
    """Return the command PROMETHEUS will run (after explicit consent) to install
    Ollama on this platform, plus a human description. Returns command=None when no
    automatic method applies and the user must install manually."""
    sysname = system or platform.system()
    if sysname == "Darwin":
        if shutil.which("brew"):
            return InstallPlan("brew install ollama", "Homebrew installs Ollama.", needs_shell=True)
        return InstallPlan(
            "curl -fsSL https://ollama.com/install.sh | sh",
            "No Homebrew found; Ollama's official installer (may request sudo).",
            needs_shell=True,
        )
    if sysname == "Linux" or _is_wsl():
        return InstallPlan(
            "curl -fsSL https://ollama.com/install.sh | sh",
            "Ollama's official installer (may request sudo internally).",
            needs_shell=True,
        )
    if sysname.startswith("Win"):
        return InstallPlan(
            "winget install Ollama.Ollama",
            "winget installs the Ollama Windows package (use WSL for the Linux path).",
            needs_shell=True,
        )
    return InstallPlan(None, f"No automatic install method for {sysname}. See https://ollama.com/download", False)


def _is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False


@dataclass
class InstallResult:
    success: bool
    output: str
    returncode: int


def run_ollama_install(plan: InstallPlan, runner=None) -> InstallResult:
    """Run the consented Ollama install command. Shell execution is intentional
    here: install plans are piped vendor scripts (e.g. `curl ... | sh`) that cannot
    be expressed as a pure argv array. The CLI MUST obtain explicit user approval
    showing plan.command before calling this."""
    if plan.command is None:
        return InstallResult(False, "No install command available.", -1)
    run = runner or subprocess.run
    completed = run(plan.command, shell=plan.needs_shell, capture_output=True, text=True)
    output = (completed.stdout or "") + (completed.stderr or "")
    return InstallResult(completed.returncode == 0, output, completed.returncode)


def start_ollama_service(base_url: str = "http://127.0.0.1:11434", runner=None) -> bool:
    """Best-effort start of the Ollama service. Returns True if the API responds
    afterwards. Never raises."""
    if check_ollama(base_url).running:
        return True
    exe = shutil.which("ollama")
    if not exe:
        return False
    run = runner or subprocess.Popen
    try:
        run([exe, "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    for _ in range(20):
        if check_ollama(base_url).running:
            return True
        import time

        time.sleep(0.5)
    return check_ollama(base_url).running


def pull_model(
    model: str,
    base_url: str = "http://127.0.0.1:11434",
    on_progress=None,
    cancel_check=None,
    client: httpx.Client | None = None,
) -> bool:
    """Pull a model via Ollama's streaming /api/pull, reporting progress through
    on_progress(dict). Returns True on success. cancel_check() -> True aborts."""
    cl = client or httpx.Client(timeout=httpx.Timeout(connect=10.0, read=None, write=10.0, pool=10.0))
    try:
        with cl.stream(
            "POST",
            f"{base_url.rstrip('/')}/api/pull",
            json={"name": model, "stream": True},
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if cancel_check and cancel_check():
                    return False
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if on_progress:
                    on_progress(data)
                if data.get("error"):
                    return False
                if data.get("status") == "success":
                    return True
        return True
    except httpx.HTTPError:
        return False
    finally:
        if client is None:
            cl.close()


def unload_model(
    model: str | None = None,
    base_url: str = "http://127.0.0.1:11434",
    client: httpx.Client | None = None,
) -> bool:
    """Free VRAM without deleting weights: keep_alive=0 evicts the model from
    memory. model=None evicts every resident model."""
    cl = client or httpx.Client(timeout=30.0)
    try:
        if model is None:
            status = check_ollama(base_url)
            if not status.running:
                return False
            ok = True
            for name in status.models:
                resp = cl.post(
                    f"{base_url.rstrip('/')}/api/generate",
                    json={"model": name, "keep_alive": 0},
                )
                if resp.status_code != 200:
                    ok = False
            return ok
        resp = cl.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "keep_alive": 0},
        )
        return resp.status_code == 200
    except httpx.HTTPError:
        return False
    finally:
        if client is None:
            cl.close()


def format_pull_progress(data: dict) -> str:
    status = data.get("status", "")
    completed = data.get("completed")
    total = data.get("total")
    if completed is not None and total:
        pct = completed * 100 // total if total else 0
        mb_done = completed / (1024 * 1024)
        mb_total = total / (1024 * 1024)
        return f"{status}: {pct}% ({mb_done:.0f}/{mb_total:.0f} MB)"
    return status


@dataclass
class SmokeResult:
    success: bool
    model: str
    response: str
    error: str = ""


def inference_smoke_test(
    model: str,
    base_url: str = "http://127.0.0.1:11434",
    client: httpx.Client | None = None,
) -> SmokeResult:
    """Run a real one-token inference probe and validate a non-empty response."""
    cl = client or httpx.Client(timeout=120.0)
    try:
        response = cl.post(
            f"{base_url.rstrip('/')}/api/generate",
            json={"model": model, "prompt": "Reply with the single word: ready", "stream": False},
        )
        if response.status_code != 200:
            return SmokeResult(False, model, "", f"HTTP {response.status_code}")
        content = response.json().get("response", "")
        if content and content.strip():
            return SmokeResult(True, model, content.strip())
        return SmokeResult(False, model, "", "empty response")
    except httpx.HTTPError as exc:
        return SmokeResult(False, model, "", str(exc))
    finally:
        if client is None:
            cl.close()
