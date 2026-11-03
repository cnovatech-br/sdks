"""The synchronous and asynchronous clients expose the same surface."""

from __future__ import annotations

import inspect

import pytest

from cnovatech.datamarket import AsyncDataMarket, DataMarket
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

PAIRS = [
    (Products, AsyncProducts),
    (Stores, AsyncStores),
    (Brands, AsyncBrands),
    (Account, AsyncAccount),
    (DataMarket, AsyncDataMarket),
]


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
