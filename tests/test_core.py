from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from prometheus_cli.hardware import HardwareReport, recommended_profile
from prometheus_cli.models import AutonomyMode, Risk, Settings
from prometheus_cli.policy import requires_approval
from prometheus_cli.tools.workspace import WorkspaceTools


class CoreTests(unittest.TestCase):
    def test_hardware_profiles(self):
        # Each forge bundle declares both minimum_ram_gb and minimum_vram_gb;
        # the host must meet both floors to be recommended it.
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Linux", architecture="x86_64", ram_gb=8, vram_gb=0)), "ember-8gb"
        )
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Linux", architecture="x86_64", ram_gb=16, vram_gb=12)), "forge-12gb"
        )
        self.assertEqual(
            recommended_profile(HardwareReport(
                os="Linux", architecture="x86_64", ram_gb=32, vram_gb=24)), "forge-24gb"
        )

    def test_cpu_only_host_never_gets_gpu_bundle_even_with_huge_ram(self):
        cpu_only_big_ram = HardwareReport(
            os="Linux", architecture="x86_64", ram_gb=47, vram_gb=0
        )
        self.assertEqual(recommended_profile(cpu_only_big_ram), "ember-8gb")

    def test_gpu_host_below_ram_floor_falls_back_to_cpu_bundle(self):
        low_ram_gpu = HardwareReport(
            os="Linux", architecture="x86_64", ram_gb=8, vram_gb=12
        )
        self.assertEqual(recommended_profile(low_ram_gpu), "ember-8gb")

    def test_gpu_host_meeting_both_floors_gets_forge(self):
        balanced = HardwareReport(
            os="Linux", architecture="x86_64", ram_gb=32, vram_gb=24
        )
        self.assertEqual(recommended_profile(balanced), "forge-24gb")

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
