from __future__ import annotations

import pytest

from cnovatech.sdk_core.pricing import batch_cost, export_cost, per_item_cost, query_cost


def test_query_cost_is_one_unit() -> None:
    assert query_cost() == 1


@pytest.mark.parametrize(
    ("rows", "expected"),
    [(0, 1), (1, 2), (100, 2), (250, 2), (251, 4), (500, 4), (1000, 8), (10_000, 80)],
)
def test_export_cost(rows: int, expected: int) -> None:
    assert export_cost(rows) == expected


@pytest.mark.parametrize(("items", "expected"), [(0, 1), (1, 1), (5, 5), (50, 50)])
def test_per_item_cost(items: int, expected: int) -> None:
    assert per_item_cost(items) == expected


@pytest.mark.parametrize(("items", "expected"), [(0, 1), (1, 1), (250, 1), (251, 2), (500, 2)])
def test_batch_cost(items: int, expected: int) -> None:
    assert batch_cost(items) == expected
