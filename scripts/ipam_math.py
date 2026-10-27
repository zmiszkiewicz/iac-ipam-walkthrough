#!/usr/bin/env python3
"""Address arithmetic for the IPAM size checks. No network access, easy to test."""
from __future__ import annotations

import ipaddress


def free_blocks(container, used):
    """Free space in `container` after removing every network in `used`.

    Returns a sorted list of the largest CIDR blocks that are still free.
    """
    parent = ipaddress.ip_network(container)
    free = [parent]
    for item in used:
        taken = ipaddress.ip_network(item)
        if not taken.overlaps(parent):
            continue
        remaining = []
        for block in free:
            if not taken.overlaps(block):
                remaining.append(block)
            elif block.subnet_of(taken):
                continue
            else:
                remaining.extend(block.address_exclude(taken))
        free = remaining
    return sorted(ipaddress.collapse_addresses(free))


def summarize(container, used):
    """Size, used and free address counts plus the free blocks for one container."""
    parent = ipaddress.ip_network(container)
    blocks = free_blocks(container, used)
    free_addresses = sum(b.num_addresses for b in blocks)
    total = parent.num_addresses
    largest = max(blocks, key=lambda b: b.num_addresses) if blocks else None
    return {
        "container": str(parent),
        "total": total,
        "used": total - free_addresses,
        "free": free_addresses,
        "percent_used": round(100.0 * (total - free_addresses) / total, 1),
        "free_blocks": [str(b) for b in blocks],
        "largest_free": str(largest) if largest else None,
    }
