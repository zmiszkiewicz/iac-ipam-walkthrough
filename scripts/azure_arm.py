#!/usr/bin/env python3
"""Read-only Azure Resource Manager queries, with no az CLI dependency.

Authenticates as the sandbox service principal from the same environment
variables Terraform's azurerm provider uses:

  ARM_CLIENT_ID  ARM_CLIENT_SECRET  ARM_TENANT_ID  ARM_SUBSCRIPTION_ID

  python3 azure_arm.py private-endpoints
"""
from __future__ import annotations

import os
import sys

import requests

ARM = "https://management.azure.com"


class AzureError(RuntimeError):
    pass


def _env(name):
    value = os.getenv(name)
    if not value:
        raise AzureError(f"{name} is not set")
    return value


def token():
    tenant = _env("ARM_TENANT_ID")
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": _env("ARM_CLIENT_ID"),
            "client_secret": _env("ARM_CLIENT_SECRET"),
            "scope": f"{ARM}/.default",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise AzureError(f"token request failed: HTTP {resp.status_code}")
    return resp.json()["access_token"]


def list_resources(path, api_version):
    """GET a list endpoint under the sandbox subscription and follow paging."""
    headers = {"Authorization": f"Bearer {token()}"}
    url = f"{ARM}/subscriptions/{_env('ARM_SUBSCRIPTION_ID')}{path}?api-version={api_version}"
    items = []
    while url:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            raise AzureError(f"GET {path}: HTTP {resp.status_code}: {resp.text[:200]}")
        body = resp.json()
        items.extend(body.get("value", []))
        url = body.get("nextLink")
    return items


def private_endpoints():
    return list_resources("/providers/Microsoft.Network/privateEndpoints", "2023-09-01")


def main():
    if sys.argv[1:] != ["private-endpoints"]:
        print(__doc__)
        return 2
    try:
        endpoints = private_endpoints()
    except AzureError as exc:
        print(f"  [FAIL] {exc}")
        return 1
    print(f"{len(endpoints)} private endpoint(s)")
    for pe in endpoints:
        print(f"  {pe['name']}  {pe['properties'].get('provisioningState')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
