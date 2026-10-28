#!/usr/bin/env python3
"""Restart the DNS service on the grid and wait until it answers again.

NIOS applies some DNS configuration changes, such as new forward zones, only
after a service restart, and a restart also empties the resolver cache. Do this
after Terraform creates or changes forward zones, or when a name still returns
a stale public answer.

  python3 restart_dns.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys

from nios_wapi import NiosWapi, WapiError, log, wait_until

DOMAIN = os.getenv("LAB_DOMAIN", "examplecorp.test")


def main():
    api = NiosWapi.from_env()
    api.detect_version()
    print(f"=== Restarting DNS on {api.host} (WAPI v{api.version}) ===")
    try:
        grid_ref = api.get("grid")[0]["_ref"]
        api.call(grid_ref, "restartservices", {
            "member_order": "SIMULTANEOUSLY",
            "service_option": "DNS",
            "restart_option": "FORCE_RESTART",
        })
    except WapiError as exc:
        print(f"  [FAIL] {exc}")
        return 1
    log("restart requested")

    if not shutil.which("dig"):
        print("  (dig not installed; not waiting for DNS to answer)")
        return 0

    name = f"web01.{DOMAIN}"

    def answers():
        out = subprocess.run(
            ["dig", "+short", "+time=3", "+tries=1", f"@{api.host}", name, "A"],
            capture_output=True, text=True, check=False).stdout.split()
        return bool(out)

    if wait_until(answers, 120, 5, "DNS to answer again"):
        log("DNS is answering")
        return 0
    log("DNS did not answer within 120s", ok=False)
    return 1


if __name__ == "__main__":
    sys.exit(main())
