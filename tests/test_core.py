from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from prometheus_cli.hardware import HardwareReport, recommended_profile
from prometheus_cli.models import AutonomyMode, Risk, Settings
from prometheus_cli.policy import requires_approval
from prometheus_cli.tools.workspace import WorkspaceTools


class CoreTests(unittest.TestCase):
    def test_hardware_profiles(self):
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Linux", architecture="x86_64", ram_gb=8, vram_gb=0, gpu_vendor=None)),
            "ember-8gb",
        )
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Linux", architecture="x86_64", ram_gb=16, vram_gb=12, gpu_vendor="NVIDIA")),
            "forge-12gb",
        )
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Linux", architecture="x86_64", ram_gb=32, vram_gb=24, gpu_vendor="AMD")),
            "forge-24gb",
        )

    def test_cpu_only_host_never_gets_gpu_bundle_even_with_huge_ram(self):
        cpu_only_big_ram = HardwareReport(
            os="Linux", architecture="x86_64", ram_gb=47, vram_gb=0, gpu_vendor=None
        )
        self.assertEqual(recommended_profile(cpu_only_big_ram), "ember-8gb")

    def test_gpu_host_below_ram_floor_falls_back_to_cpu_bundle(self):
        low_ram_gpu = HardwareReport(
            os="Linux", architecture="x86_64", ram_gb=8, vram_gb=12, gpu_vendor="NVIDIA"
        )
        self.assertEqual(recommended_profile(low_ram_gpu), "ember-8gb")

    def test_gpu_host_meeting_both_floors_gets_forge(self):
        balanced = HardwareReport(
            os="Linux", architecture="x86_64", ram_gb=32, vram_gb=24, gpu_vendor="AMD"
        )
        self.assertEqual(recommended_profile(balanced), "forge-24gb")

    def test_intel_arc_does_not_get_forge_without_capability_test(self):
        intel_arc = HardwareReport(
            os="Linux", architecture="x86_64", ram_gb=32, vram_gb=16, gpu_vendor="Intel"
        )
        self.assertEqual(recommended_profile(intel_arc), "ember-8gb")

    def test_apple_silicon_uses_unified_ram_for_profile(self):
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Darwin", architecture="arm64", ram_gb=8, gpu_vendor="Apple",
                metal=True, unified_memory=True)),
            "ember-8gb",
        )
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Darwin", architecture="arm64", ram_gb=16, gpu_vendor="Apple",
                metal=True, unified_memory=True)),
            "forge-12gb",
        )
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Darwin", architecture="arm64", ram_gb=32, gpu_vendor="Apple",
                metal=True, unified_memory=True)),
            "forge-24gb",
        )

    def test_modes_have_distinct_approval_policy(self):
        self.assertTrue(requires_approval(Settings(mode=AutonomyMode.COPILOT), Risk.WRITE))
        self.assertFalse(requires_approval(Settings(mode=AutonomyMode.PILOT), Risk.WRITE))
        self.assertTrue(requires_approval(Settings(mode=AutonomyMode.PILOT), Risk.EXECUTE))
        self.assertFalse(requires_approval(Settings(mode=AutonomyMode.ASTRONAUT), Risk.EXECUTE))
        self.assertTrue(requires_approval(Settings(mode=AutonomyMode.ASTRONAUT), Risk.DESTRUCTIVE))

    def test_workspace_cannot_escape(self):
        with TemporaryDirectory() as directory:
            tools = WorkspaceTools(Path(directory))
            with self.assertRaises(PermissionError):
                tools.read_file("../secret")

    def test_workspace_roundtrip(self):
        with TemporaryDirectory() as directory:
            tools = WorkspaceTools(Path(directory))
            tools.write_file("nested/example.txt", "hello")
            self.assertEqual(tools.read_file("nested/example.txt"), "hello")



if __name__ == "__main__":
    unittest.main()
