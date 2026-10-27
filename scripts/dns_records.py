#!/usr/bin/env python3
"""Create, change and delete DNS records through WAPI, with no Terraform.

This is the same lifecycle challenge 2 runs with Terraform, done against the raw
API so the "what can a generic client do?" question has a concrete answer. It
uses its own record names (wapi-demo) so it never touches Terraform-managed
objects.

  python3 dns_records.py show
  python3 dns_records.py create
  python3 dns_records.py change
  python3 dns_records.py delete
"""
from __future__ import annotations

import argparse
import os
import sys

from nios_wapi import NiosWapi, WapiError

DOMAIN = os.getenv("LAB_DOMAIN", "examplecorp.test")
A_NAME = f"wapi-demo.{DOMAIN}"
CNAME_NAME = f"wapi-alias.{DOMAIN}"
IP_BEFORE = "10.30.0.60"
IP_AFTER = "10.30.0.61"


def find(api, obj, **search):
    found = api.get(obj, params=search, fields=["ttl"])
    return found[0] if found and found[0] else None


def show(api):
    for obj, key in (("record:a", {"name": A_NAME}),
                     ("record:cname", {"name": CNAME_NAME}),
                     ("record:ptr", {"ptrdname": A_NAME})):
        rec = find(api, obj, **key)
        if rec is None:
            print(f"  {obj:13s} (none)")
        else:
            summary = rec.get("ipv4addr") or rec.get("canonical") or rec.get("ptrdname")
            print(f"  {obj:13s} {rec.get('name', ''):32s} -> {summary}  ttl={rec.get('ttl')}")
            print(f"  {'':13s} {rec['_ref']}")


def create(api):
    a_ref = api.post("record:a", {"name": A_NAME, "ipv4addr": IP_BEFORE, "ttl": 300,
                                   "comment": "Created through WAPI"})
    print(f"  created {a_ref}")
    ptr_ref = api.post("record:ptr", {"ptrdname": A_NAME, "ipv4addr": IP_BEFORE, "ttl": 300,
                                       "comment": "Created through WAPI"})
    print(f"  created {ptr_ref}")
    cname_ref = api.post("record:cname", {"name": CNAME_NAME, "canonical": A_NAME, "ttl": 300,
                                           "comment": "Created through WAPI"})
    print(f"  created {cname_ref}")


def change(api):
    a_rec = find(api, "record:a", name=A_NAME)
    if a_rec is None:
        raise WapiError(f"{A_NAME} does not exist. Run: python3 dns_records.py create")
    print(f"  updated {api.put(a_rec['_ref'], {'ipv4addr': IP_AFTER, 'ttl': 60})}")
    ptr_rec = find(api, "record:ptr", ptrdname=A_NAME)
    if ptr_rec is not None:
        # PTR records are keyed by address, so move it with the A record.
        print(f"  updated {api.put(ptr_rec['_ref'], {'ipv4addr': IP_AFTER, 'ttl': 60})}")


def delete(api):
    for obj, key in (("record:cname", {"name": CNAME_NAME}),
                     ("record:ptr", {"ptrdname": A_NAME}),
                     ("record:a", {"name": A_NAME})):
        rec = find(api, obj, **key)
        if rec is None:
            print(f"  {obj}: already gone")
            continue
        print(f"  deleted {api.delete(rec['_ref'])}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["show", "create", "change", "delete"])
    action = parser.parse_args().action

    api = NiosWapi.from_env()
    api.detect_version()
    print(f"=== {action} (WAPI v{api.version}, zone {DOMAIN}) ===")
    try:
        {"show": show, "create": create, "change": change, "delete": delete}[action](api)
    except WapiError as exc:
        print(f"  [FAIL] {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
