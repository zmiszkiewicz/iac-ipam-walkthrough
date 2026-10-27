#!/usr/bin/env python3
"""Small NIOS WAPI client shared by the lab scripts.

Credentials come from the environment, using the same names the Infoblox
Terraform provider reads:

  INFOBLOX_SERVER    Grid Master address (falls back to GM_IP)
  INFOBLOX_USERNAME  defaults to admin
  INFOBLOX_PASSWORD  NIOS admin password
  WAPI_VERSION       defaults to 2.12.3 (a leading "v" is optional)
  WAPI_SCHEME        https (default); the offline tests use http

2.12.3 is the WAPI version the Terraform provider is built against. Staying on
it keeps every call in this lab valid on a NIOS 8.6 grid, and newer grids still
accept it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_WAPI = "2.12.3"
FALLBACK_VERSIONS = ["2.12", "2.13.1", "2.13", "2.14"]


class WapiError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def normalize_version(version):
    """Return a bare version string: 'v2.12.3' and '2.12.3' both give '2.12.3'."""
    version = (version or DEFAULT_WAPI).strip()
    return version[1:] if version.lower().startswith("v") else version


def flatten_ea(extattrs):
    """WAPI returns {"Site": {"value": "x"}}; return {"Site": "x"}."""
    return {k: v.get("value") if isinstance(v, dict) else v for k, v in (extattrs or {}).items()}


def ea_payload(values):
    """Inverse of flatten_ea, for create and update calls."""
    return {k: {"value": v} for k, v in values.items()}


def state_dir():
    """Run-time state (grid info and so on). Never committed, see .gitignore."""
    path = Path(os.getenv("LAB_STATE_DIR") or Path(__file__).resolve().parent.parent / ".state")
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_state(name, data):
    (state_dir() / f"{name}.json").write_text(json.dumps(data, indent=2))


def load_state(name):
    path = state_dir() / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else {}


class NiosWapi:
    def __init__(self, host, username="admin", password="", version=None, timeout=30):
        self.host = host
        self.scheme = os.getenv("WAPI_SCHEME", "https")
        self.version = normalize_version(version)
        self.timeout = timeout
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.verify = False

    @classmethod
    def from_env(cls):
        host = os.getenv("INFOBLOX_SERVER") or os.getenv("GM_IP")
        password = os.getenv("INFOBLOX_PASSWORD") or os.getenv("TF_VAR_nios_admin_password")
        if not host:
            raise WapiError("INFOBLOX_SERVER (or GM_IP) is not set")
        if not password:
            raise WapiError("INFOBLOX_PASSWORD is not set")
        return cls(
            host,
            os.getenv("INFOBLOX_USERNAME", "admin"),
            password,
            os.getenv("WAPI_VERSION"),
        )

    @property
    def base(self):
        return f"{self.scheme}://{self.host}/wapi/v{self.version}"

    def _request(self, method, path, params=None, payload=None):
        url = path if path.startswith("http") else f"{self.base}/{path}"
        try:
            resp = self.session.request(
                method, url, params=params, json=payload, timeout=self.timeout
            )
        except requests.exceptions.RequestException as exc:
            raise WapiError(f"{method} {url}: {exc.__class__.__name__}: {exc}") from exc
        if not 200 <= resp.status_code < 300:
            raise WapiError(
                f"{method} {path}: HTTP {resp.status_code}: {resp.text[:300]}",
                status=resp.status_code,
            )
        return resp.json() if resp.content else None

    def detect_version(self):
        """Use the preferred WAPI version, falling back to others the grid accepts."""
        candidates = [self.version] + [v for v in FALLBACK_VERSIONS if v != self.version]
        last = None
        for candidate in candidates:
            url = f"{self.scheme}://{self.host}/wapi/v{candidate}/grid"
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.exceptions.RequestException as exc:
                raise WapiError(f"cannot reach {url}: {exc.__class__.__name__}") from exc
            if resp.status_code == 200:
                self.version = candidate
                return candidate
            if resp.status_code in (401, 403):
                raise WapiError(f"authentication failed (HTTP {resp.status_code})", status=resp.status_code)
            last = resp.status_code
        raise WapiError(f"no supported WAPI version answered (last HTTP {last})", status=last)

    def get(self, obj, params=None, fields=None, max_results=5000):
        """GET an object type or a _ref. `fields` are added to the default return fields."""
        params = dict(params or {})
        if fields:
            params["_return_fields+"] = ",".join(fields)
        if max_results and "_max_results" not in params:
            params["_max_results"] = max_results
        result = self._request("GET", obj, params=params)
        return result if isinstance(result, list) else [result]

    def post(self, obj, payload, params=None):
        return self._request("POST", obj, params=params, payload=payload)

    def put(self, ref, payload):
        return self._request("PUT", ref, payload=payload)

    def delete(self, ref):
        return self._request("DELETE", ref)

    def call(self, ref, function, payload=None):
        """Invoke a WAPI function on an object, e.g. next_available_network."""
        return self._request("POST", ref, params={"_function": function}, payload=payload or {})

    def ensure(self, obj, search, payload):
        """Create `obj` unless something matching `search` exists. Returns (ref, created)."""
        found = self.get(obj, params=search, max_results=1)
        if found and found[0]:
            return found[0]["_ref"], False
        try:
            return self.post(obj, payload), True
        except WapiError as exc:
            if exc.status == 400 and "already exists" in str(exc).lower():
                return None, False
            raise


def log(message, ok=True):
    print(f"  [{'OK' if ok else 'FAIL'}] {message}")


def wait_until(check, timeout, interval, describe):
    """Poll `check()` until it returns truthy or the timeout expires."""
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        result = check()
        if result:
            return result
        remaining = int(deadline - time.time())
        print(f"  ... waiting for {describe} (attempt {attempt}, {remaining}s left)")
        time.sleep(interval)
    return None


if __name__ == "__main__":
    api = NiosWapi.from_env()
    print(f"WAPI version in use: v{api.detect_version()}")
    print(json.dumps(api.get("grid"), indent=2))
    sys.exit(0)
