#!/usr/bin/env python3
"""Seed the Grid Master with the data the walkthrough starts from.

Everything here is created through WAPI and is safe to run twice:

  * extensible attribute definitions (including the one the Terraform provider needs)
  * network containers (supernets) and the subnets already "in use"
  * reservations that give those subnets some utilization
  * a forward zone, a reverse zone and a few host records
  * DNS service and recursion on the Grid Master

Fictional data only. The domain follows LAB_DOMAIN (default examplecorp.test).

  python3 seed_grid.py [--skip-bulk] [--skip-dns-check]
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import shutil
import subprocess
import sys
import time

from nios_wapi import NiosWapi, WapiError, ea_payload, log, save_state, wait_until

DOMAIN = os.getenv("LAB_DOMAIN", "examplecorp.test")

EA_DEFINITIONS = [
    # Terraform's provider stores its internal id here. It must exist before the
    # first apply (flags CR, per the provider documentation).
    {"name": "Terraform Internal ID", "type": "STRING", "flags": "CR",
     "comment": "Internal ID for Terraform Resource"},
    {"name": "Site", "type": "STRING", "comment": "Where the network lives"},
    {"name": "Environment", "type": "STRING", "comment": "Production, NonProd or Hub"},
    {"name": "Cloud", "type": "STRING", "comment": "OnPrem, Azure or AWS"},
    {"name": "Owner", "type": "STRING", "comment": "Team accountable for the object"},
    # Listed in the provider's prerequisites; harmless if the Cloud Network
    # Automation license already created them.
    {"name": "Tenant ID", "type": "STRING"},
    {"name": "CMP Type", "type": "STRING"},
    {"name": "Cloud API Owned", "type": "ENUM",
     "list_values": [{"value": "True"}, {"value": "False"}]},
]


def _ea(site, environment, cloud, owner):
    return {"Site": site, "Environment": environment, "Cloud": cloud, "Owner": owner}


ONPREM = _ea("HQ-DataCenter", "Production", "OnPrem", "NetOps")
AZ_PROD = _ea("Azure-NorthEurope", "Production", "Azure", "CloudOps")
AZ_NONPROD = _ea("Azure-NorthEurope", "NonProd", "Azure", "CloudOps")
AZ_HUB = _ea("Azure-NorthEurope", "Hub", "Azure", "NetOps")
AWS_PROD = _ea("AWS-EuCentral", "Production", "AWS", "CloudOps")

CONTAINERS = [
    ("10.20.0.0/16", ONPREM, "On-prem data center supernet"),
    ("10.30.0.0/16", AZ_PROD, "Azure production supernet"),
    ("10.40.0.0/16", AZ_NONPROD, "Azure non-production supernet"),
    ("10.50.0.0/16", AWS_PROD, "AWS production supernet"),
    ("10.200.0.0/16", AZ_HUB, "Azure hub VNet"),
]

# Subnets that are already in use. 10.30.2.0/23 is deliberately left free so
# the size checks have an interesting answer, and 10.40.3.0 is the first free /24.
NETWORKS = [
    ("10.20.0.0/24", ONPREM, "On-prem servers"),
    ("10.20.1.0/24", ONPREM, "On-prem users"),
    ("10.20.2.0/24", ONPREM, "On-prem voice"),
    ("10.30.0.0/24", AZ_PROD, "Production web and app"),
    ("10.30.1.0/24", AZ_PROD, "Production data"),
    ("10.30.4.0/22", AZ_PROD, "Production containers"),
    ("10.40.0.0/24", AZ_NONPROD, "Non-production dev"),
    ("10.40.1.0/24", AZ_NONPROD, "Non-production test"),
    ("10.40.2.0/24", AZ_NONPROD, "Non-production staging"),
    ("10.50.0.0/24", AWS_PROD, "AWS production"),
    ("10.200.0.0/24", AZ_HUB, "Hub DNS relay subnet"),
    ("10.200.1.0/24", AZ_HUB, "Hub private endpoint subnet"),
]

# (network, first host offset, how many, name prefix) -> utilization to look at
BULK_RESERVATIONS = [
    ("10.30.0.0/24", 100, 60, "web"),
    ("10.30.1.0/24", 10, 110, "db"),
    ("10.40.0.0/24", 10, 30, "dev"),
    ("10.40.1.0/24", 10, 190, "test"),
    ("10.40.2.0/24", 10, 12, "stg"),
]

HOSTS = {
    "web01": "10.30.0.10",
    "web02": "10.30.0.11",
    "app01": "10.30.0.20",
    "db01": "10.30.0.30",
}

REVERSE_ZONE = "10.30.0.0/24"


def seed_extensible_attributes(api):
    print("\n--- Extensible attribute definitions ---")
    for definition in EA_DEFINITIONS:
        ref, created = api.ensure("extensibleattributedef", {"name": definition["name"]}, definition)
        log(f"{definition['name']}" + ("" if created else " (exists)"))


def seed_ipam(api):
    print("\n--- Network containers ---")
    for cidr, eas, comment in CONTAINERS:
        payload = {"network": cidr, "comment": comment, "extattrs": ea_payload(eas)}
        _, created = api.ensure("networkcontainer", {"network": cidr}, payload)
        log(f"{cidr:15s} {comment}" + ("" if created else " (exists)"))

    print("\n--- Subnets already in use ---")
    for cidr, eas, comment in NETWORKS:
        payload = {"network": cidr, "comment": comment, "extattrs": ea_payload(eas)}
        _, created = api.ensure("network", {"network": cidr}, payload)
        log(f"{cidr:15s} {comment}" + ("" if created else " (exists)"))


def seed_reservations(api):
    print("\n--- Reservations (give the subnets some utilization) ---")
    use_mac = False
    for cidr, offset, count, prefix in BULK_RESERVATIONS:
        net = ipaddress.ip_network(cidr)
        created = 0
        for i in range(count):
            ip = str(net.network_address + offset + i)
            payload = {"ipv4addr": ip, "name": f"{prefix}-{i + 1:03d}", "comment": "seed",
                       "match_client": "RESERVED"}
            if use_mac:
                payload["match_client"] = "MAC_ADDRESS"
                payload["mac"] = "00:50:56:%02x:%02x:%02x" % tuple(
                    int(o) for o in ip.split(".")[1:4])
            try:
                api.post("fixedaddress", payload)
                created += 1
            except WapiError as exc:
                text = str(exc).lower()
                if "already exists" in text or "overlap" in text:
                    continue
                if not use_mac and exc.status == 400 and "mac" in text:
                    # This NIOS wants a MAC for every fixed address; retry that way.
                    use_mac = True
                    payload["match_client"] = "MAC_ADDRESS"
                    payload["mac"] = "00:50:56:%02x:%02x:%02x" % tuple(
                        int(o) for o in ip.split(".")[1:4])
                    try:
                        api.post("fixedaddress", payload)
                        created += 1
                        continue
                    except WapiError as retry_exc:
                        log(f"{ip}: {retry_exc}", ok=False)
                        return False
                log(f"{ip}: {exc}", ok=False)
                return False
        log(f"{cidr:15s} {created} new reservations ({prefix}-*)")
    return True


def seed_dns_data(api, member_hostname):
    print(f"\n--- DNS zones and hosts ({DOMAIN}) ---")
    primary = [{"_struct": "memberserver", "name": member_hostname}]

    _, created = api.ensure(
        "zone_auth", {"fqdn": DOMAIN},
        {"fqdn": DOMAIN, "view": "default", "grid_primary": primary,
         "comment": "Forward zone for the walkthrough"})
    log(f"forward zone {DOMAIN}" + ("" if created else " (exists)"))

    _, created = api.ensure(
        "zone_auth", {"fqdn": REVERSE_ZONE},
        {"fqdn": REVERSE_ZONE, "zone_format": "IPV4", "view": "default",
         "grid_primary": primary, "comment": "Reverse zone for 10.30.0.0/24"})
    log(f"reverse zone {REVERSE_ZONE}" + ("" if created else " (exists)"))

    for short, ip in HOSTS.items():
        name = f"{short}.{DOMAIN}"
        payload = {"name": name, "ipv4addrs": [{"ipv4addr": ip}], "view": "default",
                   "comment": "seed", "extattrs": ea_payload({"Owner": "app-team"})}
        _, created = api.ensure("record:host", {"name": name}, payload)
        log(f"host {name} -> {ip}" + ("" if created else " (exists)"))


def configure_dns_service(api):
    print("\n--- DNS service on the Grid Master ---")
    for member in api.get("member:dns"):
        api.put(member["_ref"], {"enable_dns": True})
        log(f"DNS enabled on {member.get('host_name', member['_ref'])}")

    grid_dns = api.get("grid:dns")[0]["_ref"]
    # The lab clients (and Terraform's dig checks) query the GM directly and need
    # it to recurse so public names such as <account>.blob.core.windows.net work.
    attempts = [
        {"allow_recursive_query": True,
         "recursive_query_list": [{"_struct": "addressac", "address": "Any", "permission": "ALLOW"}]},
        {"allow_recursive_query": True,
         "recursive_query_list": [{"_struct": "addressac", "address": "0.0.0.0/0", "permission": "ALLOW"}]},
        {"allow_recursive_query": True},
    ]
    for payload in attempts:
        try:
            api.put(grid_dns, payload)
            log("recursion enabled for all clients" if "recursive_query_list" in payload
                else "recursion enabled (query list left at its default)")
            break
        except WapiError as exc:
            if exc.status != 400:
                raise
    else:
        log("could not enable recursion; public-name lookups through the grid will fail", ok=False)
        return False

    grid_ref = api.get("grid")[0]["_ref"]
    api.call(grid_ref, "restartservices", {
        "member_order": "SIMULTANEOUSLY",
        "service_option": "DNS",
        "restart_option": "FORCE_RESTART",
    })
    log("DNS service restarted")
    return True


def wait_for_dns(api):
    """Confirm the grid really answers a query. A service flag proves nothing."""
    if not shutil.which("dig"):
        print("  (dig not installed; skipping the live DNS check)")
        return True
    name = f"web01.{DOMAIN}"
    expected = HOSTS["web01"]

    def answers():
        out = subprocess.run(
            ["dig", "+short", "+time=3", "+tries=1", f"@{api.host}", name, "A"],
            capture_output=True, text=True, check=False).stdout.split()
        return expected in out

    if wait_until(answers, 180, 10, f"{name} to resolve through the grid"):
        log(f"{name} resolves to {expected} through the grid")
        return True
    log(f"{name} did not resolve within 180s", ok=False)
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-bulk", action="store_true", help="skip the reservation loop")
    parser.add_argument("--skip-dns-check", action="store_true",
                        help="do not wait for a live DNS answer (for offline testing)")
    args = parser.parse_args()

    api = NiosWapi.from_env()
    print(f"=== Seeding the grid at {api.host} ===")
    version = api.detect_version()
    log(f"WAPI v{version}")

    members = api.get("member", fields=["host_name"])
    member_hostname = members[0]["host_name"]
    log(f"Grid Master member: {member_hostname}")

    seed_extensible_attributes(api)
    seed_ipam(api)
    if not args.skip_bulk:
        if not seed_reservations(api):
            print("  (continuing: utilization will be lower than intended)")
    seed_dns_data(api, member_hostname)
    dns_ok = configure_dns_service(api)
    if dns_ok and not args.skip_dns_check:
        time.sleep(5)
        dns_ok = wait_for_dns(api)

    save_state("grid_info", {
        "member_hostname": member_hostname,
        "wapi_version": version,
        "domain": DOMAIN,
        "gm_ip": api.host,
    })
    print("\n=== Seed complete ===" if dns_ok else "\n=== Seed finished with DNS warnings ===")
    return 0 if dns_ok else 1


if __name__ == "__main__":
    sys.exit(main())
