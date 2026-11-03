"""The Data Market tariff, in quota units, as the API publishes it.

These are estimates computed before a request is sent, for the per-request
budget guard and for pages not fetched yet. The authoritative cost of a call
is always ``usage.query_cost`` in its response.
"""

from __future__ import annotations

from cnovatech.sdk_core.pricing import block_cost, per_item_cost

QUERY_COST = 1
"""A lookup or a listing page."""

EXPORT_ROWS_PER_UNIT = 250
EXPORT_WEIGHT = 2
COVERAGE_CODES_PER_UNIT = 250


def export_cost(rows: int) -> int:
    """A page of an export: two units per started block of 250 rows."""
    return block_cost(rows, per_block=EXPORT_ROWS_PER_UNIT, weight=EXPORT_WEIGHT)


def competitor_cost(limit: int) -> int:
    """A competitor analysis: one unit per competitor returned."""
    return per_item_cost(limit)


def coverage_cost(codes: int) -> int:
    """A coverage check: one unit per started block of 250 codes."""
    return block_cost(codes, per_block=COVERAGE_CODES_PER_UNIT)
