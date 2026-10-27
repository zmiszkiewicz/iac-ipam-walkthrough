#!/usr/bin/env python3
"""Report how full each supernet is, and where the free space is.

  python3 container_report.py                    # every network container
  python3 container_report.py 10.30.0.0/16       # just one

Terraform has no data source for "how much room is left in this supernet", so
this reads the child networks through WAPI and does the arithmetic. NIOS's own
per-network utilization figure is shown alongside, untouched.
"""
from __future__ import annotations

import sys

from ipam_math import summarize
from nios_wapi import NiosWapi, WapiError


def children(api, cidr):
    """Networks and nested containers directly under `cidr`."""
    nets = api.get("network", params={"network_container": cidr}, fields=["utilization"])
    boxes = api.get("networkcontainer", params={"network_container": cidr})
    return [n for n in nets if n], [b for b in boxes if b]


def main():
    wanted = sys.argv[1:]
    api = NiosWapi.from_env()
    api.detect_version()
    print(f"=== Supernet size report (WAPI v{api.version}) ===")
    try:
        containers = api.get("networkcontainer")
    except WapiError as exc:
        print(f"  [FAIL] {exc}")
        return 1

    for box in sorted(containers, key=lambda c: tuple(int(p) for p in c["network"].split("/")[0].split("."))):
        cidr = box["network"]
        if wanted and cidr not in wanted:
            continue
        nets, boxes = children(api, cidr)
        used = [n["network"] for n in nets] + [b["network"] for b in boxes]
        info = summarize(cidr, used)
        print(f"\n  {cidr}  {box.get('comment', '')}")
        print(f"    subnets allocated : {len(nets)}")
        print(f"    addresses         : {info['total']:>8,} total, {info['used']:>8,} allocated, "
              f"{info['free']:>8,} free ({info['percent_used']}% allocated)")
        print(f"    largest free block: {info['largest_free'] or 'none'}")
        if info["free_blocks"]:
            print(f"    free blocks       : {', '.join(info['free_blocks'][:8])}"
                  + (" ..." if len(info["free_blocks"]) > 8 else ""))
        for net in sorted(nets, key=lambda n: tuple(int(p) for p in n["network"].split("/")[0].split("."))):
            print(f"      {net['network']:18s} NIOS utilization: {net.get('utilization', '-')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
