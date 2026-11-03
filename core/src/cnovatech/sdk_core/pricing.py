"""Quota cost estimates, computed before a request is sent.

These mirror the API's published pricing rules and exist for two purposes:
the optional per-request budget guard and the cost of pages not fetched yet.
The authoritative cost of a call is always ``usage.query_cost`` in its
response; the client's usage tracker only ever records that.
"""

from __future__ import annotations

import math

QUERY_COST = 1
EXPORT_ROWS_PER_UNIT = 250
EXPORT_WEIGHT = 2
BATCH_ITEMS_PER_UNIT = 250


def query_cost() -> int:
    """A lookup or a listing page: one unit."""
    return QUERY_COST


def export_cost(rows: int) -> int:
    """A page of an export: two units per started block of 250 rows, at least one."""
    return max(1, math.ceil(rows / EXPORT_ROWS_PER_UNIT) * EXPORT_WEIGHT)


def per_item_cost(items: int) -> int:
    """An analysis billed per item returned, such as one unit per competing entity."""
    return max(1, items)


def batch_cost(items: int) -> int:
    """A batch check: one unit per started block of 250 items."""
    return max(1, math.ceil(items / BATCH_ITEMS_PER_UNIT))
