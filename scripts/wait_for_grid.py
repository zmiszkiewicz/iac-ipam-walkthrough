#!/usr/bin/env python3
"""Wait until the Grid Master answers WAPI with working credentials.

A vNIOS Grid Master needs several minutes after the instance starts to boot,
apply its license and bring up the WAPI. Poll instead of sleeping for a fixed
time, and fail with a message that names what is wrong.

  python3 wait_for_grid.py [--timeout 900] [--interval 15]
"""
from __future__ import annotations

import argparse
import sys

from nios_wapi import NiosWapi, WapiError, wait_until


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--interval", type=int, default=15)
    args = parser.parse_args()

    api = NiosWapi.from_env()
    print(f"=== Waiting for the Grid Master at {api.host} (up to {args.timeout}s) ===")
    last_error = {"text": ""}

    def ready():
        try:
            api.detect_version()
            members = api.get("member", max_results=5)
            return bool(members and members[0])
        except WapiError as exc:
            last_error["text"] = str(exc)
            return False

    if wait_until(ready, args.timeout, args.interval, "the Grid Master WAPI"):
        print(f"  [OK] WAPI v{api.version} is answering on {api.host}")
        return 0

    print(f"  [FAIL] the Grid Master did not become ready within {args.timeout}s")
    print(f"         last error: {last_error['text']}")
    print("         Check the instance in the AWS console and its system log, and that")
    print("         the admin password secret was set when the instance was created.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
