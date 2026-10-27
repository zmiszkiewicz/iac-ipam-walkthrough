"""A tiny in-memory stand-in for the parts of NIOS WAPI the lab scripts use.

It is not NIOS. It exists so the scripts can be exercised offline: object
create/search/update/delete, extensible-attribute search, `network_container`
search and the next_available_* functions. Real behaviour still has to be
confirmed against a live grid.
"""
from __future__ import annotations

import ipaddress
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ipam_math import free_blocks  # noqa: E402

KEYS = {
    "network": "network", "networkcontainer": "network", "zone_auth": "fqdn",
    "extensibleattributedef": "name", "record:a": "name", "record:cname": "name",
    "record:host": "name", "fixedaddress": "ipv4addr", "record:ptr": "ipv4addr",
}


class FakeGrid:
    def __init__(self):
        self.objects = {}  # ref -> (type, dict)
        self.counter = 0
        self.add("grid", {"name": "Infoblox"})
        self.add("member", {"host_name": "gm.test.local"})
        self.add("member:dns", {"host_name": "gm.test.local", "enable_dns": False})
        self.add("grid:dns", {})

    def add(self, obj_type, data):
        self.counter += 1
        ref = f"{obj_type}/ZG{self.counter}:{data.get(KEYS.get(obj_type, 'name'), 'x')}"
        data = dict(data, _ref=ref)
        self.objects[ref] = (obj_type, data)
        return ref

    def of_type(self, obj_type):
        return [d for t, d in self.objects.values() if t == obj_type]

    def parent_container(self, cidr):
        net = ipaddress.ip_network(cidr)
        best = None
        for box in self.of_type("networkcontainer"):
            other = ipaddress.ip_network(box["network"])
            if other != net and net.subnet_of(other) and (best is None or other.prefixlen > best.prefixlen):
                best = other
        return str(best) if best else None

    def matches(self, obj_type, data, search):
        for key, want in search.items():
            if key.startswith("*"):
                if str(data.get("extattrs", {}).get(key[1:], {}).get("value")) != want:
                    return False
            elif key == "network_container":
                if self.parent_container(data["network"]) != want:
                    return False
            elif key == "ptrdname":
                if data.get("ptrdname", "").lower() != want.lower():
                    return False
            elif str(data.get(key, "")).lower() != want.lower():
                return False
        return True

    def next_networks(self, container, prefix, num):
        used = [d["network"] for d in self.of_type("network")
                if self.parent_container(d["network"]) == container]
        used += [d["network"] for d in self.of_type("networkcontainer")
                 if self.parent_container(d["network"]) == container]
        found = []
        for _ in range(num):
            for block in free_blocks(container, used):
                if block.prefixlen <= prefix:
                    pick = next(block.subnets(new_prefix=prefix))
                    found.append(str(pick))
                    used.append(str(pick))
                    break
        return found


def make_handler(grid):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):  # keep test output quiet
            pass

        def _send(self, code, body):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _route(self, method):
            import base64
            if self.headers.get("Authorization") != "Basic " + base64.b64encode(b"admin:test").decode():
                return self._send(401, {"text": "unauthorized"})
            url = urlparse(self.path)
            query = {k: v[0] for k, v in parse_qs(url.query).items()}
            path = unquote(url.path.split("/wapi/", 1)[1].split("/", 1)[1])
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length)) if length else {}

            if method == "GET":
                rows = [d for d in grid.of_type(path) if grid.matches(path, d, {
                    k: v for k, v in query.items() if not k.startswith("_")})]
                if path == "network":
                    rows = [dict(r, utilization=0) for r in rows]
                return self._send(200, rows)

            if method == "POST":
                if "_function" in query:
                    obj_type, obj = grid.objects[path]
                    func = query["_function"]
                    if func == "next_available_network":
                        return self._send(200, {"networks": grid.next_networks(
                            obj["network"], payload["cidr"], payload.get("num", 1))})
                    if func == "next_available_ip":
                        net = ipaddress.ip_network(obj["network"])
                        return self._send(200, {"ips": [str(net.network_address + 1 + i)
                                                        for i in range(payload.get("num", 1))]})
                    return self._send(200, {})
                key = KEYS.get(path, "name")
                if path == "record:ptr":
                    payload.setdefault("name", payload.get("ptrdname"))
                if any(d.get(key) == payload.get(key) for d in grid.of_type(path)):
                    return self._send(400, {"text": "already exists"})
                return self._send(201, grid.add(path, payload))

            obj_type, obj = grid.objects.get(path, (None, None))
            if obj is None:
                return self._send(404, {"text": "not found"})
            if method == "PUT":
                obj.update(payload)
                return self._send(200, path)
            if method == "DELETE":
                del grid.objects[path]
                return self._send(200, path)

        def do_GET(self):
            self._route("GET")

        def do_POST(self):
            self._route("POST")

        def do_PUT(self):
            self._route("PUT")

        def do_DELETE(self):
            self._route("DELETE")

    return Handler


def start():
    """Start the fake grid on a free local port. Returns (grid, server, "host:port")."""
    grid = FakeGrid()
    server = HTTPServer(("127.0.0.1", 0), make_handler(grid))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return grid, server, f"127.0.0.1:{server.server_address[1]}"
