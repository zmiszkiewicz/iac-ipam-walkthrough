#!/usr/bin/env python3
"""Find subnets by extensible attribute, by containing supernet, or both.

  python3 find_networks.py --containers                    # list the supernets
  python3 find_networks.py --ea Cloud=Azure                # by extensible attribute
  python3 find_networks.py --ea Cloud=Azure --ea Environment=Production
  python3 find_networks.py --container 10.30.0.0/16        # inside one supernet

A Terraform data source can filter on extensible attributes, cidr and comment.
Asking "what is inside this supernet?" is a WAPI search, so that is done here.
"""
from __future__ import annotations

import argparse
import sys

from nios_wapi import NiosWapi, WapiError, flatten_ea

EA_COLUMNS = ["Site", "Environment", "Cloud", "Owner"]


def print_table(rows, with_util):
    if not rows:
        print("  (nothing matched)")
        return
    header = f"  {'NETWORK':18s} " + " ".join(f"{c:18s}" for c in EA_COLUMNS)
    header += "  UTIL" if with_util else ""
    print(header)
    for row in rows:
        eas = flatten_ea(row.get("extattrs"))
        line = f"  {row['network']:18s} " + " ".join(f"{str(eas.get(c, '-')):18s}" for c in EA_COLUMNS)
        if with_util:
            line += f"  {row.get('utilization', '-')}"
        print(line)
    print(f"\n  {len(rows)} result(s)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ea", action="append", default=[], metavar="NAME=VALUE",
                        help="extensible attribute filter (repeatable)")
    parser.add_argument("--container", metavar="CIDR", help="only networks directly inside this supernet")
    parser.add_argument("--containers", action="store_true", help="search network containers instead of networks")
    args = parser.parse_args()

    params = {}
    for item in args.ea:
        if "=" not in item:
            parser.error(f"--ea needs NAME=VALUE, got {item!r}")
        name, value = item.split("=", 1)
        params[f"*{name}"] = value  # a leading * makes WAPI search an extensible attribute
    if args.container:
        params["network_container"] = args.container

    api = NiosWapi.from_env()
    api.detect_version()
    obj = "networkcontainer" if args.containers else "network"
    print(f"=== {obj} search (WAPI v{api.version}) ===")
    print(f"  filters: {params or 'none'}")
    try:
        rows = api.get(obj, params=params, fields=["extattrs"] + ([] if args.containers else ["utilization"]))
    except WapiError as exc:
        print(f"  [FAIL] {exc}")
        return 1
    print_table(sorted(rows, key=lambda r: tuple(int(p) for p in r["network"].split("/")[0].split("."))),
                with_util=not args.containers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
