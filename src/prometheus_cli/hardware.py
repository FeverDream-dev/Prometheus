from __future__ import annotations

import json
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass


@dataclass
class HardwareReport:
    os: str
    architecture: str
    ram_gb: float
    gpu_vendor: str | None = None
    gpu_name: str | None = None
    vram_gb: float = 0
    ollama_installed: bool = False
    docker_installed: bool = False
    wsl: bool = False

    def as_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def _ram_gb() -> float:
    try:
        import os

        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**3, 1)
    except (AttributeError, ValueError):
        return 0


def _nvidia() -> tuple[str | None, float]:
    if not shutil.which("nvidia-smi"):
        return None, 0
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True,
            timeout=5,
        ).splitlines()[0]
        name, memory = [part.strip() for part in output.rsplit(",", 1)]
        return name, round(float(memory) / 1024, 1)
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None, 0


def detect_hardware() -> HardwareReport:
    name, vram = _nvidia()
    release = platform.release().lower()
    return HardwareReport(
        os=platform.system(),
        architecture=platform.machine(),
        ram_gb=_ram_gb(),
        gpu_vendor="NVIDIA" if name else None,
        gpu_name=name,
        vram_gb=vram,
        ollama_installed=bool(shutil.which("ollama")),
        docker_installed=bool(shutil.which("docker")),
        wsl="microsoft" in release,
    )


def recommended_profile(report: HardwareReport) -> str:
    """Pick a bundle that actually fits the host.

    GPU bundles (forge-*) require both VRAM (a GPU is present) and the RAM
    minimums declared in their manifests. A CPU-only host must never receive
    a forge bundle, regardless of how much system RAM it has — its VRAM is 0
    and the bundle's models assume GPU acceleration.
    """
    if report.vram_gb >= 24 and report.ram_gb >= 32:
        return "forge-24gb"
    if report.vram_gb >= 12 and report.ram_gb >= 16:
        return "forge-12gb"
    return "ember-8gb"

