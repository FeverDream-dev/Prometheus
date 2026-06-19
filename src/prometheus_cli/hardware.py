"""Cross-platform hardware detection for PROMETHEUS.

Works on Linux, macOS, Windows/WSL across NVIDIA, AMD, Intel, Apple Silicon,
and pure CPU hosts using only the standard library. Every probe is defensive:
a missing tool or file yields a safe default and a human-readable note rather
than a crash.
"""

from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass, field

_VENDOR_AMD = "0x1002"
_VENDOR_INTEL = "0x8086"
_BYTES_PER_GB = 1024**3


@dataclass
class HardwareReport:
    os: str
    architecture: str
    ram_gb: float
    cpu_features: list[str] = field(default_factory=list)
    cpu_brand: str = ""
    gpu_vendor: str | None = None
    gpu_name: str | None = None
    vram_gb: float = 0
    metal: bool = False
    unified_memory: bool = False
    disk_free_gb: float = 0
    ollama_installed: bool = False
    docker_installed: bool = False
    wsl: bool = False
    notes: list[str] = field(default_factory=list)

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _run(cmd: list[str], *, timeout: float = 5.0) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return None


def _which(name: str) -> bool:
    return shutil.which(name) is not None


def _ram_gb_linux() -> float:
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        return round(page_size * pages / _BYTES_PER_GB, 1)
    except (AttributeError, ValueError, OSError):
        pass
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024**2, 1)
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def _ram_gb_macos() -> float:
    result = _run(["sysctl", "-n", "hw.memsize"])
    if result and result.returncode == 0:
        try:
            return round(int(result.stdout.strip()) / _BYTES_PER_GB, 1)
        except ValueError:
            pass
    return 0.0


def _ram_gb_windows() -> float:
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))  # type: ignore[attr-defined]
        return round(stat.ullTotalPhys / _BYTES_PER_GB, 1)
    except (AttributeError, OSError, ValueError):
        return 0.0


def _ram_gb() -> float:
    system = platform.system()
    if system == "Darwin":
        return _ram_gb_macos()
    if system == "Windows":
        return _ram_gb_windows()
    return _ram_gb_linux()


def _probe_nvidia() -> tuple[str | None, float]:
    if not _which("nvidia-smi"):
        return None, 0.0
    result = _run(
        ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
        timeout=5.0,
    )
    if not result or result.returncode != 0 or not result.stdout.strip():
        return None, 0.0
    try:
        first = result.stdout.splitlines()[0]
        name, memory_mib = [part.strip() for part in first.rsplit(",", 1)]
        return name, round(float(memory_mib) / 1024, 1)
    except (ValueError, IndexError):
        return None, 0.0


def _read_sysfs(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError:
        return None


def _probe_drm_linux(vendor_id: str, default_name: str) -> tuple[str | None, float]:
    base = "/sys/class/drm"
    try:
        cards = sorted(os.listdir(base))
    except OSError:
        return None, 0.0
    for card in cards:
        if not card.startswith("card"):
            continue
        if _read_sysfs(os.path.join(base, card, "device", "vendor")) != vendor_id:
            continue
        product = _read_sysfs(os.path.join(base, card, "device", "product_name"))
        name = product or default_name
        vram_bytes = _read_sysfs(os.path.join(base, card, "device", "mem_info", "vram_total"))
        vram = round(int(vram_bytes) / _BYTES_PER_GB, 1) if vram_bytes else 0.0
        return name, vram
    return None, 0.0


def _probe_amd_linux() -> tuple[str | None, float]:
    return _probe_drm_linux(_VENDOR_AMD, "AMD GPU")


def _probe_intel_linux() -> tuple[str | None, float]:
    return _probe_drm_linux(_VENDOR_INTEL, "Intel GPU")


def _classify_gpu_name(name: str) -> str:
    lower = name.lower()
    if "nvidia" in lower or "geforce" in lower or "rtx" in lower or "quadro" in lower:
        return "NVIDIA"
    if "amd" in lower or "radeon" in lower or "ryzen" in lower:
        return "AMD"
    if "intel" in lower or "arc" in lower:
        return "Intel"
    return "Unknown"


def _probe_windows_gpus() -> list[tuple[str, str, int]]:
    ps = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterRAM,VideoProcessor | ConvertTo-Json"
    )
    result = _run(["powershell", "-NoProfile", "-Command", ps], timeout=8.0)
    if not result or result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    items = data if isinstance(data, list) else [data]
    out: list[tuple[str, str, int]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or item.get("VideoProcessor") or "")
        vram_bytes = int(item.get("AdapterRAM") or 0)
        out.append((_classify_gpu_name(name), name, vram_bytes))
    return out


def _probe_apple_gpu() -> tuple[str | None, bool]:
    brand = _cpu_brand_macos().lower()
    is_apple_silicon = "apple m" in brand or "apple s" in brand
    result = _run(["system_profiler", "SPDisplaysDataType"], timeout=8.0)
    if not result or result.returncode != 0:
        return None, is_apple_silicon
    name: str | None = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if "Chipset Model" in stripped:
            name = stripped.split(":", 1)[1].strip()
            break
    return name, is_apple_silicon


def _cpu_features_linux() -> list[str]:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("flags") or line.startswith("Features"):
                    return line.split(":", 1)[1].strip().split()
    except OSError:
        pass
    return []


def _cpu_features_macos() -> list[str]:
    features: list[str] = []
    for key in ("machdep.cpu.features", "machdep.cpu.leaf7_features"):
        result = _run(["sysctl", "-n", key])
        if result and result.returncode == 0 and result.stdout.strip():
            features.extend(result.stdout.strip().lower().split())
    return features


def _cpu_features() -> list[str]:
    system = platform.system()
    if system == "Darwin":
        return _cpu_features_macos()
    if system == "Linux":
        return _cpu_features_linux()
    return []


def _cpu_brand_macos() -> str:
    result = _run(["sysctl", "-n", "machdep.cpu.brand_string"])
    if result and result.returncode == 0:
        return result.stdout.strip()
    return ""


def _cpu_brand_linux() -> str:
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return ""


def _cpu_brand() -> str:
    system = platform.system()
    if system == "Darwin":
        return _cpu_brand_macos()
    if system == "Linux":
        return _cpu_brand_linux()
    return platform.processor() or ""


def _disk_free_gb(path: str | None = None) -> float:
    try:
        usage = shutil.disk_usage(path or os.getcwd())
        return round(usage.free / _BYTES_PER_GB, 1)
    except OSError:
        return 0.0


def detect_hardware() -> HardwareReport:
    system = platform.system()
    release = platform.release().lower()
    ram = _ram_gb()
    notes: list[str] = []

    gpu_vendor: str | None = None
    gpu_name: str | None = None
    vram = 0.0
    metal = False
    unified = False

    nv_name, nv_vram = _probe_nvidia()
    if nv_name:
        gpu_vendor, gpu_name, vram = "NVIDIA", nv_name, nv_vram

    if system == "Darwin":
        apple_name, is_silicon = _probe_apple_gpu()
        if apple_name:
            gpu_vendor = gpu_vendor or "Apple"
            gpu_name = gpu_name or apple_name
            metal = True
            unified = is_silicon
            notes.append(
                "Apple Silicon unified memory: model size limited by RAM."
                if is_silicon
                else "Apple Metal available on a discrete GPU."
            )
        else:
            notes.append("No Apple GPU detected via system_profiler.")

    if system == "Linux" and gpu_vendor is None:
        amd_name, amd_vram = _probe_amd_linux()
        if amd_name:
            gpu_vendor, gpu_name, vram = "AMD", amd_name, amd_vram
        else:
            intel_name, intel_vram = _probe_intel_linux()
            if intel_name:
                gpu_vendor, gpu_name, vram = "Intel", intel_name, intel_vram

    if system == "Windows" and not nv_name:
        gpus = _probe_windows_gpus()
        priority = {"NVIDIA": 0, "AMD": 1, "Intel": 2, "Unknown": 3}
        best = min(gpus, key=lambda g: priority.get(g[0], 9)) if gpus else None
        if best:
            gpu_vendor, gpu_name = best[0], best[1]
            vram = round(best[2] / _BYTES_PER_GB, 1)

    if gpu_vendor is None:
        notes.append("No accelerated GPU detected; PROMETHEUS will run in CPU mode.")
    if ram == 0:
        notes.append("Could not determine total RAM; bundle recommendation may be wrong.")

    return HardwareReport(
        os=system,
        architecture=platform.machine(),
        ram_gb=ram,
        cpu_features=_cpu_features(),
        cpu_brand=_cpu_brand(),
        gpu_vendor=gpu_vendor,
        gpu_name=gpu_name,
        vram_gb=vram,
        metal=metal,
        unified_memory=unified,
        disk_free_gb=_disk_free_gb(),
        ollama_installed=_which("ollama"),
        docker_installed=_which("docker"),
        wsl="microsoft" in release,
        notes=notes,
    )


def recommended_profile(report: HardwareReport) -> str:
    """Pick a bundle that fits the host without overpromising acceleration.

    Apple Silicon shares system RAM with the GPU, so its profile is gated on
    total RAM. Dedicated NVIDIA/AMD GPUs require both their VRAM and the RAM
    floor. Intel Arc, unverified accelerators, and CPU-only hosts always fall
    back to the ember profile until a capability test proves tool-call
    reliability on that backend.
    """
    if report.metal and report.unified_memory:
        if report.ram_gb >= 32:
            return "forge-24gb"
        if report.ram_gb >= 16:
            return "forge-12gb"
        return "ember-8gb"

    if report.gpu_vendor in {"NVIDIA", "AMD"}:
        if report.vram_gb >= 24 and report.ram_gb >= 32:
            return "forge-24gb"
        if report.vram_gb >= 12 and report.ram_gb >= 16:
            return "forge-12gb"

    return "ember-8gb"
