"""Live system telemetry for the PROMETHEUS TUI and CLI.

Cross-platform sampler that collects CPU/RAM/disk/GPU/Ollama/git/sandbox state
for the right-hand telemetry panel and the ``prometheus telemetry`` command.

Design constraints:
  * ``psutil`` is OPTIONAL. When absent, CPU/RAM/disk fall back to stdlib probes
    (``/proc/stat``, ``/proc/meminfo``, ``shutil.disk_usage``).
  * GPU usage probes (``nvidia-smi`` / ``rocm-smi``) run with a strict timeout
    and never crash the TUI if they fail or are absent.
  * Expensive probes (GPU output) are cached for ~1s so the 1-2s refresh loop
    does not fork a subprocess on every tick.
  * No secret/private data is collected. ``git`` status reports counts only.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_BYTES_PER_GB = 1024**3
_GPU_CACHE_TTL_S = 1.0
_gpu_cache: dict[str, tuple[float, dict]] = {}


def _try_psutil():
    try:
        import psutil  # type: ignore[import-not-found]
    except ImportError:
        return None
    return psutil


def _read_proc_stat() -> tuple[int, int] | None:
    try:
        with open("/proc/stat", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("cpu "):
                    parts = line.split()
                    vals = [int(p) for p in parts[1:]]
                    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                    total = sum(vals)
                    return idle, total
    except (OSError, ValueError, IndexError):
        return None
    return None


def sample_cpu_percent(interval_s: float = 0.1) -> float | None:
    psutil = _try_psutil()
    if psutil is not None:
        try:
            v = psutil.cpu_percent(interval=interval_s)
            return round(v, 1)
        except Exception:
            return None
    if platform.system() != "Linux":
        return None
    first = _read_proc_stat()
    if first is None:
        return None
    time.sleep(max(0.05, min(interval_s, 0.5)))
    second = _read_proc_stat()
    if second is None:
        return None
    idle1, total1 = first
    idle2, total2 = second
    dt = total2 - total1
    di = idle2 - idle1
    if dt <= 0:
        return None
    return round(max(0.0, min(100.0, (1.0 - di / dt) * 100.0)), 1)


def sample_ram() -> dict:
    psutil = _try_psutil()
    if psutil is not None:
        try:
            vm = psutil.virtual_memory()
            return {
                "total_gb": round(vm.total / _BYTES_PER_GB, 1),
                "used_gb": round(vm.used / _BYTES_PER_GB, 1),
                "percent": round(vm.percent, 1),
            }
        except Exception:
            pass
    if platform.system() == "Linux":
        try:
            total_kb = avail_kb = 0
            with open("/proc/meminfo", encoding="utf-8") as handle:
                for line in handle:
                    if line.startswith("MemTotal:"):
                        total_kb = int(line.split()[1])
                    elif line.startswith("MemAvailable:"):
                        avail_kb = int(line.split()[1])
            if total_kb > 0:
                used_kb = total_kb - avail_kb
                return {
                    "total_gb": round(total_kb / 1024**2, 1),
                    "used_gb": round(used_kb / 1024**2, 1),
                    "percent": round(used_kb / total_kb * 100.0, 1),
                }
        except (OSError, ValueError, IndexError):
            pass
    return {"total_gb": 0.0, "used_gb": 0.0, "percent": 0.0}


def sample_disk(path: str | None = None) -> dict:
    target = path or os.getcwd()
    try:
        usage = shutil.disk_usage(target)
        used = usage.total - usage.free
        return {
            "path": target,
            "total_gb": round(usage.total / _BYTES_PER_GB, 1),
            "used_gb": round(used / _BYTES_PER_GB, 1),
            "percent": round(used / usage.total * 100.0, 1) if usage.total else 0.0,
        }
    except OSError:
        return {"path": target, "total_gb": 0.0, "used_gb": 0.0, "percent": 0.0}


def sample_battery() -> dict | None:
    psutil = _try_psutil()
    if psutil is None:
        return None
    try:
        bat = psutil.sensors_battery()
        if bat is None:
            return None
        return {"percent": round(bat.percent, 1), "plugged": bool(bat.power_plugged)}
    except Exception:
        return None


def _run(cmd: list[str], timeout: float) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None


def parse_nvidia_smi(output: str) -> dict:
    """Parse ``nvidia-smi --query-gpu=... --format=csv,noheader,nounits`` output.

    Expected first-line shape: ``NVIDIA GeForce RTX 4070, 35, 4567, 8192, 42``
    corresponding to name, utilization.gpu, memory.used (MiB), memory.total,
    temperature. Missing columns are tolerated.
    """
    out: dict = {
        "vendor": "NVIDIA", "name": None, "usage_percent": None,
        "vram_used_gb": None, "vram_total_gb": None, "vram_percent": None,
        "temperature_c": None, "available": True,
    }
    line = output.strip().splitlines()[0] if output.strip() else ""
    if not line:
        out["available"] = False
        return out
    parts = [p.strip() for p in line.split(",")]
    if not parts:
        out["available"] = False
        return out
    out["name"] = parts[0]
    if len(parts) >= 2 and parts[1].isdigit():
        out["usage_percent"] = float(parts[1])
    if len(parts) >= 3 and parts[2].isdigit():
        out["vram_used_gb"] = round(int(parts[2]) / 1024, 2)
    if len(parts) >= 4 and parts[3].isdigit():
        out["vram_total_gb"] = round(int(parts[3]) / 1024, 2)
    if out["vram_used_gb"] is not None and out["vram_total_gb"]:
        out["vram_percent"] = round(out["vram_used_gb"] / out["vram_total_gb"] * 100.0, 1)
    if len(parts) >= 5 and parts[4].isdigit():
        out["temperature_c"] = float(parts[4])
    return out


def parse_rocm_smi(output: str) -> dict:
    """Parse ``rocm-smi --showuse --showmeminfo vram --json`` output.

    Expected shape (one JSON object per card):
    ``{"card0": {"GPU use (%)": "35", "VRAM Total Memory (B)": "17163091968",
                  "VRAM Total Used Memory (B)": "4567890123"}}``
    """
    out: dict = {
        "vendor": "AMD", "name": None, "usage_percent": None,
        "vram_used_gb": None, "vram_total_gb": None, "vram_percent": None,
        "temperature_c": None, "available": False,
    }
    if not output.strip():
        return out
    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        return out
    if not isinstance(data, dict) or not data:
        return out
    first_key = next(iter(data))
    card = data[first_key]
    if not isinstance(card, dict):
        return out
    out["available"] = True
    out["name"] = card.get("Card series") or card.get("Card model") or "AMD GPU"
    usage = card.get("GPU use (%)")
    if isinstance(usage, str):
        try:
            out["usage_percent"] = float(usage)
        except ValueError:
            pass
    vram_total = card.get("VRAM Total Memory (B)")
    vram_used = card.get("VRAM Total Used Memory (B)")
    if vram_total and str(vram_total).isdigit():
        out["vram_total_gb"] = round(int(vram_total) / _BYTES_PER_GB, 2)
    if vram_used and str(vram_used).isdigit():
        out["vram_used_gb"] = round(int(vram_used) / _BYTES_PER_GB, 2)
    if out["vram_used_gb"] is not None and out["vram_total_gb"]:
        out["vram_percent"] = round(out["vram_used_gb"] / out["vram_total_gb"] * 100.0, 1)
    return out


def sample_gpu(timeout_s: float = 1.5) -> dict:
    cache_key = f"gpu::{timeout_s}"
    now = time.monotonic()
    cached = _gpu_cache.get(cache_key)
    if cached and (now - cached[0]) < _GPU_CACHE_TTL_S:
        return cached[1]

    result: dict = {
        "vendor": None, "name": None, "usage_percent": None,
        "vram_used_gb": None, "vram_total_gb": None, "vram_percent": None,
        "temperature_c": None, "available": False, "source": None,
    }

    if shutil.which("nvidia-smi"):
        completed = _run(
            ["nvidia-smi",
             "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            timeout=timeout_s,
        )
        if completed and completed.returncode == 0 and completed.stdout.strip():
            parsed = parse_nvidia_smi(completed.stdout)
            if parsed.get("available"):
                result = {**result, **parsed, "source": "nvidia-smi"}

    if not result["available"] and shutil.which("rocm-smi"):
        completed = _run(
            ["rocm-smi", "--showuse", "--showmeminfo", "vram", "--json"],
            timeout=timeout_s,
        )
        if completed and completed.returncode == 0 and completed.stdout.strip():
            parsed = parse_rocm_smi(completed.stdout)
            if parsed.get("available"):
                result = {**result, **parsed, "source": "rocm-smi"}

    if not result["available"]:
        try:
            from .hardware import detect_hardware
            report = detect_hardware()
            if report.gpu_vendor:
                result = {
                    **result,
                    "vendor": report.gpu_vendor,
                    "name": report.gpu_name or report.gpu_vendor,
                    "vram_total_gb": report.vram_gb or None,
                    "available": False,
                    "source": "hardware-detect (usage probe unavailable)",
                }
        except Exception:
            pass

    _gpu_cache[cache_key] = (now, result)
    return result


def sample_ollama(base_url: str = "http://127.0.0.1:11434") -> dict:
    try:
        from .onboarding import check_ollama
        status = check_ollama(base_url)
        return {
            "running": status.running,
            "installed": status.installed,
            "model_count": len(status.models),
            "models": status.models[:8],
        }
    except Exception as exc:
        return {"running": False, "installed": False, "model_count": 0,
                "models": [], "error": str(exc)[:120]}


def sample_git(workspace: str | Path | None = None) -> dict:
    ws = str(workspace or os.getcwd())
    if not Path(ws, ".git").exists() and not Path(ws, ".git").is_file():
        return {"available": False, "branch": None, "dirty": False, "modified_files": 0}
    branch_result = _run(["git", "-C", ws, "rev-parse", "--abbrev-ref", "HEAD"], timeout=1.0)
    status_result = _run(["git", "-C", ws, "status", "--porcelain"], timeout=1.0)
    branch = None
    dirty = False
    modified = 0
    if branch_result and branch_result.returncode == 0:
        branch = branch_result.stdout.strip() or None
    if status_result and status_result.returncode == 0:
        lines = [ln for ln in status_result.stdout.splitlines() if ln.strip()]
        modified = len(lines)
        dirty = modified > 0
    return {
        "available": True, "branch": branch, "dirty": dirty, "modified_files": modified,
    }


def sample_sandbox() -> dict:
    try:
        from .config import load_settings
        settings = load_settings()
        return {
            "tier": settings.effective_sandbox_tier().value,
            "policy_enabled": settings.sandbox,
        }
    except Exception as exc:
        return {"tier": "off", "policy_enabled": False, "error": str(exc)[:120]}


def sample_bundle() -> dict:
    try:
        from .config import load_settings
        settings = load_settings()
        return {
            "active_id": settings.active_bundle_id,
            "provider": "openai-compat" if not settings.local_only else "ollama-only",
        }
    except Exception as exc:
        return {"active_id": None, "provider": None, "error": str(exc)[:120]}


@dataclass
class TelemetrySnapshot:
    timestamp: str
    cpu_percent: float | None
    ram: dict
    disk: dict
    gpu: dict
    battery: dict | None
    ollama: dict
    git: dict
    sandbox: dict
    bundle: dict
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), indent=2, sort_keys=False)


def collect_snapshot(
    workspace: str | Path | None = None,
    gpu_timeout_s: float = 1.5,
    cpu_interval_s: float = 0.1,
) -> TelemetrySnapshot:
    notes: list[str] = []
    cpu = sample_cpu_percent(interval_s=cpu_interval_s)
    if cpu is None:
        notes.append("CPU percent unavailable (psutil missing and not Linux).")
    gpu = sample_gpu(timeout_s=gpu_timeout_s)
    if not gpu.get("available"):
        notes.append(
            f"GPU usage probe unavailable ({gpu.get('source', 'no vendor tool')}); "
            "name shown when detectable."
        )
    return TelemetrySnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        cpu_percent=cpu,
        ram=sample_ram(),
        disk=sample_disk(str(workspace) if workspace else None),
        gpu=gpu,
        battery=sample_battery(),
        ollama=sample_ollama(),
        git=sample_git(workspace),
        sandbox=sample_sandbox(),
        bundle=sample_bundle(),
        notes=notes,
    )


def render_bar(percent: float | None, width: int = 10) -> str:
    if percent is None:
        return "░" * width
    clamped = max(0.0, min(100.0, float(percent)))
    filled = int(round(clamped / 100.0 * width))
    return "█" * filled + "░" * (width - filled)


def _percent_label(percent: float | None) -> str:
    if percent is None:
        return "n/a"
    return f"{round(percent):>3d}%"


def render_telemetry_lines(snapshot: TelemetrySnapshot) -> list[str]:
    cpu = snapshot.cpu_percent
    ram_pct = snapshot.ram.get("percent")
    disk_pct = snapshot.disk.get("percent")
    gpu = snapshot.gpu

    lines = [
        f"[bold]System telemetry[/bold]  [dim]{snapshot.timestamp}[/dim]",
        "",
        f"  CPU    {render_bar(cpu)}  {_percent_label(cpu)}",
        (f"  RAM    {render_bar(ram_pct)}  {_percent_label(ram_pct)}"
         f"  {snapshot.ram.get('used_gb', 0):.1f}/{snapshot.ram.get('total_gb', 0):.1f} GB"),
        (f"  DISK   {render_bar(disk_pct)}  {_percent_label(disk_pct)}"
         f"  {snapshot.disk.get('used_gb', 0):.0f}/{snapshot.disk.get('total_gb', 0):.0f} GB"),
    ]

    if gpu.get("name"):
        usage = gpu.get("usage_percent")
        if usage is not None:
            lines.append(f"  GPU    {render_bar(usage)}  {_percent_label(usage)}  {gpu['name']}")
        else:
            lines.append(f"  GPU    {gpu.get('name', 'unknown')} — usage unavailable")
        vram_pct = gpu.get("vram_percent")
        if vram_pct is not None:
            lines.append(
                f"  VRAM   {render_bar(vram_pct)}  {_percent_label(vram_pct)}"
                f"  {gpu.get('vram_used_gb', 0):.1f}/{gpu.get('vram_total_gb', 0):.1f} GB"
            )
        else:
            lines.append("  VRAM   unavailable")
    else:
        lines.append("  GPU    not detected (CPU-only mode)")
        lines.append("  VRAM   unavailable")

    if snapshot.battery:
        lines.append(
            f"  BAT    {render_bar(snapshot.battery['percent'])}"
            f"  {_percent_label(snapshot.battery['percent'])}"
            f"  {'plugged' if snapshot.battery['plugged'] else 'on battery'}"
        )

    lines.append("")
    ollama = snapshot.ollama
    ollama_state = "OK" if ollama.get("running") else "[red]down[/red]"
    lines.append(f"  Ollama: {ollama_state} ({ollama.get('model_count', 0)} models)")

    git = snapshot.git
    if git.get("available"):
        dirty_tag = "[yellow]dirty[/yellow]" if git.get("dirty") else "[green]clean[/green]"
        branch = git.get("branch") or "(detached)"
        lines.append(f"  Git:    {branch} · {dirty_tag} · {git.get('modified_files', 0)} changes")

    sb = snapshot.sandbox
    lines.append(f"  Sandbox: {sb.get('tier', 'off')} (policy {'on' if sb.get('policy_enabled') else 'off'})")

    bundle = snapshot.bundle
    if bundle.get("active_id"):
        lines.append(f"  Bundle: {bundle['active_id']} ({bundle.get('provider', '?')})")
    else:
        lines.append("  Bundle: [yellow]none configured[/yellow]")

    for note in snapshot.notes:
        lines.append(f"  [dim]• {note}[/dim]")

    return lines


__all__ = [
    "TelemetrySnapshot",
    "collect_snapshot",
    "parse_nvidia_smi",
    "parse_rocm_smi",
    "render_bar",
    "render_telemetry_lines",
    "sample_battery",
    "sample_cpu_percent",
    "sample_disk",
    "sample_git",
    "sample_gpu",
    "sample_ollama",
    "sample_ram",
    "sample_sandbox",
]
