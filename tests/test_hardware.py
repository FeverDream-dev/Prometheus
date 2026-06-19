from __future__ import annotations

import subprocess
from unittest import mock

from prometheus_cli import hardware


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class TestRamDetection:
    def test_macos_ram_parses_hw_memsize_bytes(self):
        with mock.patch.object(hardware, "_run", return_value=_completed(str(34 * 1024**3))):
            assert hardware._ram_gb_macos() == 34.0

    def test_macos_ram_returns_zero_when_sysctl_fails(self):
        with mock.patch.object(hardware, "_run", return_value=None):
            assert hardware._ram_gb_macos() == 0.0

    def test_linux_ram_falls_back_to_meminfo(self, tmp_path):
        meminfo = tmp_path / "meminfo"
        meminfo.write_text("MemTotal:       16384000 kB\n")
        with mock.patch.object(hardware.os, "sysconf", side_effect=ValueError), \
             mock.patch("builtins.open", mock.mock_open(read_data=meminfo.read_text())):
            assert hardware._ram_gb_linux() == round(16384000 / 1024**2, 1)

    def test_windows_ram_returns_zero_without_ctypes_windll(self):
        with mock.patch.object(hardware.ctypes, "windll", create=True, side_effect=AttributeError):
            assert hardware._ram_gb_windows() == 0.0


class TestGpuDetection:
    def test_nvidia_parses_smi_csv(self):
        csv = "NVIDIA GeForce RTX 4090, 24564"
        with mock.patch.object(hardware, "_which", return_value=True), \
             mock.patch.object(hardware, "_run", return_value=_completed(csv)):
            name, vram = hardware._probe_nvidia()
            assert name == "NVIDIA GeForce RTX 4090"
            assert vram == 24.0

    def test_nvidia_returns_none_without_smi(self):
        with mock.patch.object(hardware, "_which", return_value=False):
            assert hardware._probe_nvidia() == (None, 0.0)

    def test_classify_gpu_name(self):
        assert hardware._classify_gpu_name("NVIDIA GeForce RTX 4060") == "NVIDIA"
        assert hardware._classify_gpu_name("AMD Radeon RX 7900") == "AMD"
        assert hardware._classify_gpu_name("Intel Arc A770") == "Intel"
        assert hardware._classify_gpu_name("Mystery GPU") == "Unknown"

    def test_amd_sysfs_probe_reads_vendor_and_vram(self):
        def fake_read(path):
            if path.endswith("vendor"):
                return hardware._VENDOR_AMD
            if path.endswith("product_name"):
                return "AMD Radeon RX 7900 XTX"
            if path.endswith("vram_total"):
                return str(24 * hardware._BYTES_PER_GB)
            return None

        with mock.patch.object(hardware.os, "listdir", return_value=["card0", "card1"]), \
             mock.patch.object(hardware, "_read_sysfs", side_effect=fake_read):
            name, vram = hardware._probe_amd_linux()
            assert name == "AMD Radeon RX 7900 XTX"
            assert vram == 24.0

    def test_drm_probe_skips_non_matching_vendor(self):
        calls = []

        def fake_read(path):
            calls.append(path)
            if path.endswith("vendor"):
                return "0x1234"
            return None

        with mock.patch.object(hardware.os, "listdir", return_value=["card0"]), \
             mock.patch.object(hardware, "_read_sysfs", side_effect=fake_read):
            name, vram = hardware._probe_amd_linux()
            assert name is None
            assert vram == 0.0

    def test_apple_silicon_detected_from_brand(self):
        with mock.patch.object(hardware, "_cpu_brand_macos", return_value="Apple M3 Max"), \
             mock.patch.object(hardware, "_run",
                               return_value=_completed("    Chipset Model: Apple M3 Max\n")):
            name, is_silicon = hardware._probe_apple_gpu()
            assert name == "Apple M3 Max"
            assert is_silicon is True

    def test_apple_discrete_gpu_not_flagged_as_unified(self):
        with mock.patch.object(hardware, "_cpu_brand_macos", return_value="Intel Core i7"), \
             mock.patch.object(hardware, "_run",
                               return_value=_completed("    Chipset Model: AMD Radeon Pro 5500\n")):
            name, is_silicon = hardware._probe_apple_gpu()
            assert name == "AMD Radeon Pro 5500"
            assert is_silicon is False


class TestDiskDetection:
    def test_disk_free_gb_positive(self, tmp_path):
        assert hardware._disk_free_gb(str(tmp_path)) > 0

    def test_disk_free_gb_zero_on_bad_path(self):
        assert hardware._disk_free_gb("/nonexistent/path/that/does/not/exist") == 0.0


class TestDetectHardwareDispatch:
    def test_detect_on_linux_invokes_linux_probes(self):
        with mock.patch.object(hardware.platform, "system", return_value="Linux"), \
             mock.patch.object(hardware.platform, "release", return_value="6.5.0"), \
             mock.patch.object(hardware.platform, "machine", return_value="x86_64"), \
             mock.patch.object(hardware, "_ram_gb", return_value=16.0), \
             mock.patch.object(hardware, "_probe_nvidia", return_value=(None, 0.0)), \
             mock.patch.object(hardware, "_probe_amd_linux", return_value=("AMD Radeon", 12.0)), \
             mock.patch.object(hardware, "_cpu_features", return_value=["avx2"]), \
             mock.patch.object(hardware, "_cpu_brand", return_value="AMD Ryzen 7"), \
             mock.patch.object(hardware, "_disk_free_gb", return_value=100.0), \
             mock.patch.object(hardware, "_which", return_value=False):
            report = hardware.detect_hardware()
            assert report.os == "Linux"
            assert report.gpu_vendor == "AMD"
            assert report.vram_gb == 12.0
            assert report.ram_gb == 16.0
            assert report.wsl is False

    def test_detect_on_macos_flags_metal_and_unified(self):
        with mock.patch.object(hardware.platform, "system", return_value="Darwin"), \
             mock.patch.object(hardware.platform, "release", return_value="23.0"), \
             mock.patch.object(hardware.platform, "machine", return_value="arm64"), \
             mock.patch.object(hardware, "_ram_gb", return_value=16.0), \
             mock.patch.object(hardware, "_probe_nvidia", return_value=(None, 0.0)), \
             mock.patch.object(hardware, "_probe_apple_gpu",
                               return_value=("Apple M2 Pro", True)), \
             mock.patch.object(hardware, "_cpu_features", return_value=[]), \
             mock.patch.object(hardware, "_cpu_brand", return_value="Apple M2 Pro"), \
             mock.patch.object(hardware, "_disk_free_gb", return_value=200.0), \
             mock.patch.object(hardware, "_which", return_value=True):
            report = hardware.detect_hardware()
            assert report.gpu_vendor == "Apple"
            assert report.metal is True
            assert report.unified_memory is True
            assert any("unified memory" in n for n in report.notes)

    def test_detect_on_wsl_sets_wsl_flag(self):
        with mock.patch.object(hardware.platform, "system", return_value="Linux"), \
             mock.patch.object(hardware.platform, "release", return_value="5.15-microsoft-standard"), \
             mock.patch.object(hardware.platform, "machine", return_value="x86_64"), \
             mock.patch.object(hardware, "_ram_gb", return_value=32.0), \
             mock.patch.object(hardware, "_probe_nvidia", return_value=(None, 0.0)), \
             mock.patch.object(hardware, "_probe_amd_linux", return_value=(None, 0.0)), \
             mock.patch.object(hardware, "_probe_intel_linux", return_value=(None, 0.0)), \
             mock.patch.object(hardware, "_cpu_features", return_value=[]), \
             mock.patch.object(hardware, "_cpu_brand", return_value=""), \
             mock.patch.object(hardware, "_disk_free_gb", return_value=50.0), \
             mock.patch.object(hardware, "_which", return_value=False):
            report = hardware.detect_hardware()
            assert report.wsl is True
            assert report.gpu_vendor is None
            assert any("CPU mode" in n for n in report.notes)
