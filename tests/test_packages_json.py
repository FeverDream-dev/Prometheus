"""Drift guard for the website model-package comparison (section 10).

``website/packages.json`` is the data source for the interactive package
comparison on the site. It is generated from ``config/bundles-v2/*.yaml``.
These tests assert the two cannot drift: the package count and the ordered id
list must match, every controller model tag must match, and the
quota-free / metered distinction must agree with the manifests.

If you add or rename a bundle, regenerate ``website/packages.json`` from the
YAML or these tests fail.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is a project dependency
    yaml = None


REPO = Path(__file__).resolve().parent.parent
BUNDLES_DIR = REPO / "config" / "bundles-v2"
PACKAGES_JSON = REPO / "website" / "packages.json"


def _load_bundles():
    files = sorted(BUNDLES_DIR.glob("*.yaml"))
    docs = []
    for f in files:
        docs.append(yaml.safe_load(f.read_text(encoding="utf-8")))
    return docs


class PackagesJsonDriftTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if yaml is None:
            raise unittest.SkipTest("PyYAML not installed")
        cls.bundles = _load_bundles()
        cls.doc = json.loads(PACKAGES_JSON.read_text(encoding="utf-8"))
        cls.packages = cls.doc["packages"]

    def test_count_matches_bundles(self):
        self.assertEqual(len(self.packages), len(self.bundles))

    def test_ordered_ids_match_bundles(self):
        bundle_ids = [b["id"] for b in self.bundles]
        pkg_ids = [p["id"] for p in self.packages]
        self.assertEqual(pkg_ids, bundle_ids)

    def test_controller_model_tags_match(self):
        by_id = {p["id"]: p for p in self.packages}
        for b in self.bundles:
            pkg = by_id[b["id"]]
            roles = b.get("roles", {})
            controller = roles.get("controller")
            if controller is None:
                # Add-on only (e.g. VibeThinker): no controller role allowed.
                self.assertFalse(any(r["role"] == "controller" for r in pkg["roles"]),
                                 f"{b['id']} must have no controller")
                continue
            pkg_controller = next(r for r in pkg["roles"] if r["role"] == "controller")
            self.assertEqual(pkg_controller["model"], controller["model"], b["id"])

    def test_unlimited_local_flag_matches(self):
        by_id = {p["id"]: p for p in self.packages}
        for b in self.bundles:
            pkg = by_id[b["id"]]
            expected = bool(b["runtime"].get("unlimited_local_sessions", True))
            self.assertEqual(pkg["unlimited_local_sessions"], expected, b["id"])

    def test_hardware_minimums_match(self):
        by_id = {p["id"]: p for p in self.packages}
        for b in self.bundles:
            pkg = by_id[b["id"]]
            hw = b["hardware"]
            self.assertEqual(pkg["min_ram_gb"], hw["minimum_ram_gb"], b["id"])
            self.assertEqual(pkg["min_vram_gb"], hw["minimum_vram_gb"], b["id"])

    def test_vibethinker_is_addon_and_never_controller(self):
        by_id = {p["id"]: p for p in self.packages}
        vt = by_id["vibethinker-review-addon"]
        self.assertTrue(vt["addon"])
        self.assertFalse(any(r["role"] == "controller" for r in vt["roles"]))
        reviewer = next(r for r in vt["roles"] if r["role"] == "reviewer")
        self.assertIn("tools", reviewer.get("prohibited_capabilities", []))

    def test_core_download_is_sum_of_required_roles(self):
        for p in self.packages:
            required = [r["download_gb"] for r in p["roles"] if not r.get("optional")]
            if not required:
                continue
            expected = round(sum(required), 3)
            self.assertAlmostEqual(p["core_download_gb"], expected, places=2, msg=p["id"])

    def test_all_packages_with_expected_names(self):
        names = {p["name"] for p in self.packages}
        self.assertEqual(
            names,
            {"Spark", "Ember", "Forge", "Oracle", "Titan", "Hephaestus", "VibeThinker", "Cloud-Hybrid"},
        )

    def test_repo_field_is_correct(self):
        self.assertEqual(self.doc["repo"], "FeverDream-dev/Prometheus")


if __name__ == "__main__":
    unittest.main()
