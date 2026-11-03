from __future__ import annotations

import pytest

from cnovatech.sdk_core.pricing import block_cost, per_item_cost


@pytest.mark.parametrize(
    ("items", "expected"),
    [(0, 1), (1, 2), (100, 2), (250, 2), (251, 4), (500, 4), (1000, 8), (10_000, 80)],
)
def test_block_cost_with_weight(items: int, expected: int) -> None:
    assert block_cost(items, per_block=250, weight=2) == expected


@pytest.mark.parametrize(("items", "expected"), [(0, 1), (1, 1), (250, 1), (251, 2), (500, 2)])
def test_block_cost_without_weight(items: int, expected: int) -> None:
    assert block_cost(items, per_block=250) == expected


@pytest.mark.parametrize(("items", "expected"), [(0, 1), (1, 1), (5, 5), (50, 50)])
def test_per_item_cost(items: int, expected: int) -> None:
    assert per_item_cost(items) == expected
