#!/usr/bin/env python3
"""Remove the <participant>-infoblox record that setup_dns.py created.

Best effort by design: this runs from the track's cleanup script, where a
non-zero exit must never stop the rest of the teardown. It always exits 0.
"""
from __future__ import annotations

import sys

from setup_dns import record_name, required, route53


def main():
    try:
        client = route53()
        zone = required("DEMO_HOSTED_ZONE_ID")
        fqdn = record_name()
        found = client.list_resource_record_sets(
            HostedZoneId=zone, StartRecordName=fqdn, StartRecordType="A", MaxItems="1")
        records = [r for r in found["ResourceRecordSets"] if r["Name"] == fqdn and r["Type"] == "A"]
        if not records:
            print(f"  {fqdn}: nothing to delete")
            return 0
        client.change_resource_record_sets(
            HostedZoneId=zone,
            ChangeBatch={"Changes": [{"Action": "DELETE", "ResourceRecordSet": records[0]}]})
        print(f"  [OK] deleted {fqdn}")
    except (SystemExit, Exception) as exc:  # noqa: BLE001 - teardown must not fail
        print(f"  WARNING: DNS cleanup skipped: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
