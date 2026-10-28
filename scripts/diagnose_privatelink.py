#!/usr/bin/env python3
"""Explain why Private Link names do or do not resolve privately through the grid.

  python3 diagnose_privatelink.py

Prints how each NIOS forward zone is configured, then resolves each private
endpoint name through the grid and says what the answer means.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

from nios_wapi import NiosWapi, WapiError

REPO_ROOT = Path(__file__).resolve().parent.parent
IPV4 = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
ZONES = ["privatelink.blob.core.windows.net", "privatelink.file.core.windows.net"]


def classify(answers):
    """Say what an answer for a privatelink name means."""
    ips = [a for a in answers if IPV4.match(a)]
    if any(ip.startswith("10.200.") for ip in ips):
        return "private", "resolves to a private address: the forward zone is working"
    if ips:
        return "public", ("resolves to a PUBLIC address: the grid is not using the forward zone "
                          "(zone not applied or assigned yet, or an old answer is cached)")
    return "none", ("no answer: the grid tried to forward but got nothing back "
                    "(DNS relay VM not up yet, or its network rule does not admit the grid)")


def dig(server, name):
    return subprocess.run(["dig", "+short", "+time=5", "+tries=2", f"@{server}", name, "A"],
                          capture_output=True, text=True, check=False).stdout.split()


def endpoint_names():
    result = subprocess.run(
        ["terraform", f"-chdir={REPO_ROOT / 'terraform' / '04-privatelink'}",
         "output", "-json", "names_to_resolve"],
        capture_output=True, text=True, check=False)
    return json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else {}


def main():
    api = NiosWapi.from_env()
    api.detect_version()
    print(f"=== Private Link diagnosis (grid {api.host}, WAPI v{api.version}) ===\n")

    print("-- NIOS forward zones --")
    fields = ["disable", "forward_to", "forwarders_only", "forwarding_servers", "ns_group", "external_ns_group"]
    for fqdn in ZONES:
        try:
            found = api.get("zone_forward", params={"fqdn": fqdn}, fields=fields)
        except WapiError as exc:
            print(f"  {fqdn}: [FAIL] {exc}")
            continue
        if not found or not found[0]:
            print(f"  {fqdn}: MISSING")
            continue
        zone = found[0]
        targets = [f"{t.get('address')}" for t in zone.get("forward_to", [])]
        members = [m.get("name") for m in zone.get("forwarding_servers", [])]
        print(f"  {fqdn}")
        print(f"      forwards to      : {targets or 'NOTHING'}")
        print(f"      assigned members : {members or 'NONE (no member serves this zone)'}")
        print(f"      forward only     : {zone.get('forwarders_only')}   disabled: {zone.get('disable')}")

    print("\n-- Resolving through the grid --")
    names = endpoint_names()
    if not names:
        print("  no private endpoints in Terraform state yet (run terraform apply in 04-privatelink)")
        return 0
    verdicts = set()
    for key, privatelink_name in sorted(names.items()):
        public_name = privatelink_name.replace(".privatelink.", ".")
        for label, name in (("privatelink name", privatelink_name), ("public name", public_name)):
            answers = dig(api.host, name)
            verdict, meaning = classify(answers)
            verdicts.add(verdict)
            print(f"  {key:10s} {label:16s} {name}")
            print(f"             -> {', '.join(answers) or '(empty)'}   [{verdict}] {meaning}")

    print()
    if verdicts == {"private"}:
        print("All names resolve privately.")
    elif "public" in verdicts:
        print("Next step: python3 restart_dns.py   (applies pending DNS changes and clears the cache),")
        print("then run this again. If a name is still public, a forward zone has no member assigned.")
    else:
        print("Next step: the DNS relay VM. Give it a few minutes after the baseline apply, then run this again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
