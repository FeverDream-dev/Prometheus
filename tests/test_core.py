from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from prometheus_cli.hardware import HardwareReport, recommended_profile
from prometheus_cli.models import AutonomyMode, Risk, Settings
from prometheus_cli.policy import requires_approval
from prometheus_cli.tools.workspace import WorkspaceTools


class CoreTests(unittest.TestCase):
    def test_hardware_profiles(self):
        base = dict(os="Linux", architecture="x86_64", ram_gb=8)
        self.assertEqual(recommended_profile(HardwareReport(**base, vram_gb=0)), "ember-8gb")
        self.assertEqual(recommended_profile(HardwareReport(**base, vram_gb=12)), "forge-12gb")
        self.assertEqual(recommended_profile(HardwareReport(**base, vram_gb=24)), "forge-24gb")

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
