"""Offline tests: pure helpers plus the scripts run against the fake WAPI.

    python3 -m unittest discover -s scripts/tests

These prove the scripts' own logic. They cannot prove NIOS accepts a payload;
that needs a live grid (see README, "What was not tested").
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fake_wapi  # noqa: E402
from ipam_math import free_blocks, summarize  # noqa: E402
from make_tfvars import hcl  # noqa: E402
from nios_wapi import NiosWapi, WapiError, ea_payload, flatten_ea, normalize_version  # noqa: E402


class HelperTests(unittest.TestCase):
    def test_version_normalisation(self):
        self.assertEqual(normalize_version("v2.12.3"), "2.12.3")
        self.assertEqual(normalize_version("2.12.3"), "2.12.3")
        self.assertEqual(normalize_version(None), "2.12.3")

    def test_ea_round_trip(self):
        eas = {"Site": "HQ", "Owner": "NetOps"}
        self.assertEqual(flatten_ea(ea_payload(eas)), eas)
        self.assertEqual(flatten_ea(None), {})

    def test_free_blocks_leaves_the_gap(self):
        used = ["10.30.0.0/24", "10.30.1.0/24", "10.30.4.0/22"]
        blocks = [str(b) for b in free_blocks("10.30.0.0/16", used)]
        self.assertIn("10.30.2.0/23", blocks)
        self.assertNotIn("10.30.0.0/24", blocks)
        self.assertEqual(blocks[-1], "10.30.128.0/17")

    def test_free_blocks_full_and_empty(self):
        self.assertEqual(free_blocks("10.0.0.0/24", ["10.0.0.0/24"]), [])
        self.assertEqual([str(b) for b in free_blocks("10.0.0.0/24", [])], ["10.0.0.0/24"])

    def test_summary_counts_add_up(self):
        info = summarize("10.30.0.0/16", ["10.30.0.0/24", "10.30.1.0/24", "10.30.4.0/22"])
        self.assertEqual(info["used"], 256 + 256 + 1024)
        self.assertEqual(info["used"] + info["free"], info["total"])
        self.assertEqual(info["largest_free"], "10.30.128.0/17")

    def test_hcl_rendering(self):
        self.assertEqual(hcl("a${b}"), '"a$${b}"')
        self.assertEqual(hcl(True), "true")
        self.assertEqual(hcl(["x", "y"]), '["x", "y"]')
        self.assertEqual(hcl({"blob": "1", "a b": "2"}), '{\n  "a b" = "2"\n  blob  = "1"\n}')
        self.assertEqual(hcl({"a-b": "2"}), '{\n  a-b = "2"\n}')


class ScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid, cls.server, cls.host = fake_wapi.start()
        cls.env = dict(os.environ, INFOBLOX_SERVER=cls.host, INFOBLOX_USERNAME="admin",
                       INFOBLOX_PASSWORD="test", WAPI_SCHEME="http", LAB_DOMAIN="examplecorp.test",
                       LAB_STATE_DIR=str(SCRIPTS / ".test-state"))
        cls.env.pop("WAPI_VERSION", None)
        # 1) The seed has to succeed before anything else makes sense.
        out = cls.run_script("seed_grid.py", "--skip-dns-check")
        assert out.returncode == 0, out.stdout + out.stderr

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    @classmethod
    def run_script(cls, name, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / name), *args], env=cls.env,
                              capture_output=True, text=True, timeout=120, check=False)

    def test_bad_password_is_reported_not_crashed(self):
        api = NiosWapi(self.host, "admin", "wrong")
        os.environ["WAPI_SCHEME"] = "http"
        try:
            with self.assertRaises(WapiError):
                api.detect_version()
        finally:
            os.environ.pop("WAPI_SCHEME", None)

    def test_seed_is_idempotent(self):
        before = len(self.grid.objects)
        out = self.run_script("seed_grid.py", "--skip-dns-check")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(len(self.grid.objects), before, "a second seed run created objects")

    def test_seed_creates_the_expected_objects(self):
        self.assertEqual(len(self.grid.of_type("networkcontainer")), 5)
        self.assertEqual(len(self.grid.of_type("network")), 12)
        self.assertEqual(len(self.grid.of_type("zone_auth")), 2)
        self.assertEqual(len(self.grid.of_type("record:host")), 4)
        self.assertEqual(len(self.grid.of_type("fixedaddress")), 60 + 110 + 30 + 190 + 12)
        names = {d["name"] for d in self.grid.of_type("extensibleattributedef")}
        self.assertIn("Terraform Internal ID", names)
        flags = [d.get("flags") for d in self.grid.of_type("extensibleattributedef")
                 if d["name"] == "Terraform Internal ID"]
        self.assertEqual(flags, ["CR"])
        self.assertTrue(self.grid.of_type("member:dns")[0]["enable_dns"])

    def test_find_by_ea(self):
        out = self.run_script("find_networks.py", "--ea", "Cloud=Azure", "--ea", "Environment=Production")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("10.30.0.0/24", out.stdout)
        self.assertNotIn("10.40.0.0/24", out.stdout)
        self.assertIn("3 result(s)", out.stdout)

    def test_find_by_container(self):
        out = self.run_script("find_networks.py", "--container", "10.40.0.0/16")
        self.assertIn("10.40.2.0/24", out.stdout)
        self.assertNotIn("10.30.0.0/24", out.stdout)

    def test_container_report(self):
        out = self.run_script("container_report.py", "10.30.0.0/16")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("largest free block: 10.30.128.0/17", out.stdout)
        self.assertIn("10.30.2.0/23", out.stdout)

    def test_next_available_does_not_allocate(self):
        before = len(self.grid.of_type("network"))
        out = self.run_script("next_available.py", "--container", "10.40.0.0/16", "--prefix", "24", "--num", "3")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        for expected in ("10.40.3.0/24", "10.40.4.0/24", "10.40.5.0/24"):
            self.assertIn(expected, out.stdout)
        self.assertIn("nothing was allocated", out.stdout)
        self.assertEqual(len(self.grid.of_type("network")), before)

    def test_next_available_ips(self):
        out = self.run_script("next_available.py", "--network", "10.40.0.0/24", "--ips", "2")
        self.assertIn("10.40.0.1", out.stdout)

    def test_dns_lifecycle(self):
        self.assertEqual(self.run_script("dns_records.py", "create").returncode, 0)
        shown = self.run_script("dns_records.py", "show").stdout
        self.assertIn("10.30.0.60", shown)
        self.assertEqual(self.run_script("dns_records.py", "change").returncode, 0)
        shown = self.run_script("dns_records.py", "show").stdout
        self.assertIn("10.30.0.61", shown)
        self.assertIn("ttl=60", shown)
        self.assertEqual(self.run_script("dns_records.py", "delete").returncode, 0)
        self.assertIn("(none)", self.run_script("dns_records.py", "show").stdout)
        # deleting twice is harmless
        self.assertEqual(self.run_script("dns_records.py", "delete").returncode, 0)

    def test_change_before_create_gives_a_clear_error(self):
        self.run_script("dns_records.py", "delete")
        out = self.run_script("dns_records.py", "change")
        self.assertEqual(out.returncode, 1)
        self.assertIn("create", out.stdout)

    def test_verify_ipam_stage(self):
        reason = Path("/tmp/lab_check_reason.txt")
        out = self.run_script("verify_lab.py", "--stage", "ipam")
        self.assertEqual(out.returncode, 1)
        self.assertIn("0 of 3", reason.read_text())
        for name, prefix in (("app-tier", 24), ("data-tier", 25), ("mgmt", 26)):
            ref = self.grid.add("network", {
                "network": f"10.40.{3 + len(name) % 3}.0/{prefix}",
                "comment": f"Provisioned by Terraform: {name}"})
            self.assertTrue(ref)
        out = self.run_script("verify_lab.py", "--stage", "ipam")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)


if __name__ == "__main__":
    unittest.main()
