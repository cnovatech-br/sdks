"""The published tariff, as the SDK estimates it before sending."""

from __future__ import annotations

import pytest

from cnovatech.datamarket.resources._pricing import (
    QUERY_COST,
    competitor_cost,
    coverage_cost,
    export_cost,
)


def test_a_query_costs_one_unit() -> None:
    assert QUERY_COST == 1


@pytest.mark.parametrize(
    ("rows", "expected"),
    [(1, 2), (100, 2), (250, 2), (251, 4), (1000, 8), (10_000, 80)],
)
def test_export_cost(rows: int, expected: int) -> None:
    assert export_cost(rows) == expected


@pytest.mark.parametrize(("limit", "expected"), [(1, 1), (5, 5), (50, 50)])
def test_competitor_cost(limit: int, expected: int) -> None:
    assert competitor_cost(limit) == expected


@pytest.mark.parametrize(("codes", "expected"), [(1, 1), (250, 1), (251, 2), (500, 2)])
def test_coverage_cost(codes: int, expected: int) -> None:
    assert coverage_cost(codes) == expected
