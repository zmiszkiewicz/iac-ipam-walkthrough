#!/usr/bin/env python3
"""Ask Infoblox what is next available, WITHOUT allocating anything.

  python3 next_available.py --container 10.40.0.0/16 --prefix 24 --num 3
  python3 next_available.py --network 10.40.0.0/24 --ips 5

The next-available functions only report; nothing is created until a client
(Terraform, a script, a pipeline) posts the result back. That is what makes them
safe for a "can we fit it?" check before a change request.
"""
from __future__ import annotations

import argparse
import sys

from nios_wapi import NiosWapi, WapiError


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--container", metavar="CIDR", help="network container to look in")
    parser.add_argument("--prefix", type=int, help="prefix length wanted, e.g. 24")
    parser.add_argument("--num", type=int, default=1, help="how many networks")
    parser.add_argument("--network", metavar="CIDR", help="network to take free addresses from")
    parser.add_argument("--ips", type=int, help="how many free addresses")
    args = parser.parse_args()

    api = NiosWapi.from_env()
    api.detect_version()
    print(f"=== Next available (WAPI v{api.version}) ===")
    try:
        if args.container:
            if not args.prefix:
                parser.error("--container needs --prefix")
            box = api.get("networkcontainer", params={"network": args.container})
            if not box or not box[0]:
                print(f"  [FAIL] no network container {args.container}")
                return 1
            before = len(api.get("network", params={"network_container": args.container}))
            result = api.call(box[0]["_ref"], "next_available_network",
                              {"cidr": args.prefix, "num": args.num})
            print(f"  next {args.num} free /{args.prefix} in {args.container}:")
            for net in result.get("networks", []):
                print(f"    {net}")
            after = len(api.get("network", params={"network_container": args.container}))
            print(f"\n  networks in {args.container}: {before} before, {after} after "
                  f"-> nothing was allocated")
        elif args.network:
            if not args.ips:
                parser.error("--network needs --ips")
            net = api.get("network", params={"network": args.network})
            if not net or not net[0]:
                print(f"  [FAIL] no network {args.network}")
                return 1
            result = api.call(net[0]["_ref"], "next_available_ip", {"num": args.ips})
            print(f"  next {args.ips} free address(es) in {args.network}:")
            for ip in result.get("ips", []):
                print(f"    {ip}")
            print("\n  nothing was reserved")
        else:
            parser.error("give --container with --prefix, or --network with --ips")
    except WapiError as exc:
        print(f"  [FAIL] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
