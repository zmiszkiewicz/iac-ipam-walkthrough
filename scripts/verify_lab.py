#!/usr/bin/env python3
"""Check that a challenge's objects really exist. Used by the track's check-shell.

  python3 verify_lab.py --stage baseline|dns|ipam|privatelink

Looks at state, not at what was typed: records and subnets are read back from
the grid, and Private Link names are resolved through the grid with dig. On
failure a one-sentence reason is written to /tmp/lab_check_reason.txt, which
check-shell hands to Instruqt as the failure message.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from nios_wapi import NiosWapi, WapiError

REASON_FILE = Path("/tmp/lab_check_reason.txt")
DOMAIN = os.getenv("LAB_DOMAIN", "examplecorp.test")
REPO_ROOT = Path(__file__).resolve().parent.parent
IPV4 = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


class Check(Exception):
    """Raised with the sentence to show the presenter."""


def dig(server, name):
    out = subprocess.run(
        ["dig", "+short", "+time=5", "+tries=2", f"@{server}", name, "A"],
        capture_output=True, text=True, check=False).stdout.split()
    return [line for line in out if IPV4.match(line)]


def one(api, obj, **search):
    found = api.get(obj, params=search, fields=["ttl"] if obj.startswith("record:") else None)
    return found[0] if found and found[0] else None


def stage_baseline(api):
    if not api.get("member"):
        raise Check("The Grid Master has no members yet. Wait a minute and check again.")
    if not one(api, "extensibleattributedef", name="Terraform Internal ID"):
        raise Check("The 'Terraform Internal ID' extensible attribute is missing. Run: python3 seed_grid.py")
    if not one(api, "zone_auth", fqdn=DOMAIN):
        raise Check(f"The {DOMAIN} zone is missing. Run: python3 seed_grid.py")
    supernets = api.get("networkcontainer")
    if len([s for s in supernets if s]) < 4:
        raise Check("The seeded supernets are missing. Run: python3 seed_grid.py")
    if "10.30.0.10" not in dig(api.host, f"web01.{DOMAIN}"):
        raise Check(f"web01.{DOMAIN} does not resolve through the grid yet. DNS may still be starting.")


def stage_dns(api):
    a_rec = one(api, "record:a", name=f"demo-app.{DOMAIN}")
    if not a_rec:
        raise Check(f"demo-app.{DOMAIN} does not exist. In terraform/02-dns-records run: terraform apply")
    if not one(api, "record:ptr", ptrdname=f"demo-app.{DOMAIN}"):
        raise Check("The PTR record for demo-app does not exist. Run terraform apply in 02-dns-records.")
    if a_rec["ipv4addr"] not in dig(api.host, f"demo-app.{DOMAIN}"):
        raise Check(f"demo-app.{DOMAIN} exists in NIOS but the grid does not answer for it.")


def stage_ipam(api):
    carved = [n for n in api.get("network", params={"network_container": "10.40.0.0/16"})
              if n and n.get("comment", "").startswith("Provisioned by Terraform")]
    if len(carved) < 3:
        raise Check(f"{len(carved)} of 3 subnets were allocated from 10.40.0.0/16. "
                    "In terraform/03-ipam run: terraform apply -parallelism=1")


def terraform_output(stage, name):
    result = subprocess.run(
        ["terraform", f"-chdir={REPO_ROOT / 'terraform' / stage}", "output", "-json", name],
        capture_output=True, text=True, check=False)
    return json.loads(result.stdout) if result.returncode == 0 and result.stdout.strip() else None


def stage_privatelink(api):
    for namespace in ("privatelink.blob.core.windows.net", "privatelink.file.core.windows.net"):
        zone = one(api, "zone_forward", fqdn=namespace)
        if not zone:
            raise Check(f"No NIOS forward zone for {namespace}. In terraform/04-privatelink run: terraform apply")
    names = terraform_output("04-privatelink", "names_to_resolve")
    if not names:
        raise Check("No private endpoints have been created yet. Add endpoints.auto.tfvars and run terraform apply.")
    unresolved = [n for n in names.values() if not any(ip.startswith("10.200.") for ip in dig(api.host, n))]
    if unresolved:
        raise Check(f"{unresolved[0]} did not resolve to a private 10.200.x.x address through the grid. "
                    "Run restart_dns.py so the grid applies the forward zones, then check again.")


STAGES = {"baseline": stage_baseline, "dns": stage_dns, "ipam": stage_ipam, "privatelink": stage_privatelink}


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--stage", required=True, choices=sorted(STAGES))
    stage = parser.parse_args().stage

    REASON_FILE.unlink(missing_ok=True)
    try:
        api = NiosWapi.from_env()
        api.detect_version()
        STAGES[stage](api)
    except Check as exc:
        REASON_FILE.write_text(str(exc))
        print(f"  [FAIL] {exc}")
        return 1
    except WapiError as exc:
        REASON_FILE.write_text(f"Could not talk to the Grid Master: {exc}")
        print(f"  [FAIL] {exc}")
        return 1
    print(f"  [OK] stage '{stage}' verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
