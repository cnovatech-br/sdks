"""Shapes of quota cost estimates, computed before a request is sent.

The numbers of a tariff belong to the product SDK that publishes them; the
core only knows how a cost is shaped. Estimates exist for the optional
per-request budget guard and for the cost of pages not fetched yet. The
authoritative cost of a call is always ``usage.query_cost`` in its response.
"""

from __future__ import annotations

import math


def block_cost(items: int, *, per_block: int, weight: int = 1) -> int:
    """``weight`` units per started block of ``per_block`` items, at least one unit."""
    return max(1, math.ceil(items / per_block) * weight)


def per_item_cost(items: int) -> int:
    """One unit per item returned, at least one unit."""
    return max(1, items)
