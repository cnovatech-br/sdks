"""The synchronous and asynchronous clients expose the same surface."""

from __future__ import annotations

import inspect
import re
from typing import TYPE_CHECKING

import pytest
from conftest import load_fixture

from cnovatech.datamarket import AsyncDataMarket, DataMarket, errors
from cnovatech.datamarket.resources import (
    Account,
    AsyncAccount,
    AsyncBrands,
    AsyncProducts,
    AsyncStores,
    Brands,
    Products,
    Stores,
)

if TYPE_CHECKING:
    from conftest import FakeAPI

PAIRS = [
    (Products, AsyncProducts),
    (Stores, AsyncStores),
    (Brands, AsyncBrands),
    (Account, AsyncAccount),
    (DataMarket, AsyncDataMarket),
]

STORE_ID = load_fixture("getStoreAssortment.json")["store"]["store_id"]
COMPETITOR_ID = load_fixture("getCompetitorProducts.json")["competitor"]["store_id"]
# "``limit=1000`` costs 8" and "``limit`` up to 100 costs 2", as the docstrings put it.
STATED_COST = re.compile(r"limit(?:=|`` up to )(\d+)(?:``)? costs (\d+)")


def public_methods(cls: type) -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(member)
        for name, member in inspect.getmembers(cls, inspect.isfunction)
        if not name.startswith("_")
    }


@pytest.mark.parametrize(("sync_cls", "async_cls"), PAIRS, ids=lambda cls: cls.__name__)
def test_same_methods_with_the_same_parameters(sync_cls: type, async_cls: type) -> None:
    sync_methods = public_methods(sync_cls)
    async_methods = public_methods(async_cls)
    renamed = {"close": "aclose"}

    assert {renamed.get(name, name) for name in sync_methods} == set(async_methods)
    for name, signature in sync_methods.items():
        counterpart = async_methods[renamed.get(name, name)]
        assert list(signature.parameters.values()) == list(counterpart.parameters.values()), name


@pytest.mark.parametrize(("sync_cls", "async_cls"), PAIRS[:4], ids=lambda cls: cls.__name__)
def test_async_methods_are_coroutines(sync_cls: type, async_cls: type) -> None:
    for name in public_methods(sync_cls):
        assert inspect.iscoroutinefunction(getattr(async_cls, name)), name
        assert not inspect.iscoroutinefunction(getattr(sync_cls, name)), name


def test_every_resource_method_states_its_cost() -> None:
    for cls in (Products, Stores, Brands):
        for name, member in inspect.getmembers(cls, inspect.isfunction):
            if name.startswith("_"):
                continue
            assert member.__doc__ is not None, f"{cls.__name__}.{name}"
            assert "Cost:" in member.__doc__, f"{cls.__name__}.{name}"


def test_the_costs_the_docstrings_state_are_the_ones_estimated(api: FakeAPI) -> None:
    """Every ``limit=N costs M`` in a store docstring is checked against the budget guard."""
    checked = 0
    for name, member in inspect.getmembers(Stores, inspect.isfunction):
        docstring = " ".join((member.__doc__ or "").split())
        for limit, cost in STATED_COST.findall(docstring):
            identifiers = (STORE_ID, COMPETITOR_ID) if name == "compare" else (STORE_ID,)
            with (
                api.client(max_units_per_request=int(cost) - 1) as client,
                pytest.raises(errors.BudgetExceededError) as excinfo,
            ):
                getattr(client.stores, name)(*identifiers, limit=int(limit))
            assert excinfo.value.estimated_cost == int(cost), f"{name}: limit={limit}"
            checked += 1

    assert checked >= 4, "the docstrings of the export methods state their costs"
    assert api.requests == []


def test_competitor_analyses_cost_one_unit_per_competitor(api: FakeAPI) -> None:
    for name in ("competitors", "competitiveness"):
        with (
            api.client(max_units_per_request=2) as client,
            pytest.raises(errors.BudgetExceededError) as excinfo,
        ):
            getattr(client.stores, name)(STORE_ID, limit=3)
        assert excinfo.value.estimated_cost == 3, name

    assert api.requests == []
