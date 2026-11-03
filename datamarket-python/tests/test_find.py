"""Lookup of a store by name across result pages."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from cnovatech.datamarket import errors
from cnovatech.datamarket.resources.stores import FIND_MAX_PAGES

if TYPE_CHECKING:
    from conftest import FakeAPI

STORES = "/api/v1/market/stores"


def stores_page(page: int, pages: int, *names: str) -> dict[str, Any]:
    return {
        "data": [
            {
                "store_id": f"{page:04x}{index:04x}-0000-4000-8000-000000000000",
                "store_name": name,
                "state": "SP",
            }
            for index, name in enumerate(names)
        ],
        "meta": {"page": page, "limit": 100, "total": 100 * pages, "pages": pages},
        "usage": {"query_cost": 1},
    }


def test_exact_match_on_a_later_page_is_found(api: FakeAPI) -> None:
    api.respond(
        "GET", STORES, stores_page(1, 2, "Mercado Azul", "Mercado Verde"), params={"page": "1"}
    )
    api.respond("GET", STORES, stores_page(2, 2, "Mercado", "Mercado Rosa"), params={"page": "2"})

    with api.client() as client:
        found = client.stores.find("mercado")

    assert found.store_name == "Mercado"
    assert [dict(request.url.params)["page"] for request in api.requests] == ["1", "2"]
    assert client.usage.spent == 2


def test_search_stops_at_the_page_with_the_exact_match(api: FakeAPI) -> None:
    api.respond("GET", STORES, stores_page(1, 3, "Mercado", "Mercado Verde"), params={"page": "1"})

    with api.client() as client:
        found = client.stores.find("Mercado")

    assert found.store_name == "Mercado"
    assert len(api.requests) == 1


def test_candidates_from_every_page_are_reported_when_none_is_exact(api: FakeAPI) -> None:
    api.respond(
        "GET", STORES, stores_page(1, 2, "Mercado Azul", "Mercado Verde"), params={"page": "1"}
    )
    api.respond("GET", STORES, stores_page(2, 2, "Mercado Rosa"), params={"page": "2"})

    with api.client() as client, pytest.raises(errors.AmbiguousStoreError) as excinfo:
        client.stores.find("Mercado")

    assert [store.store_name for store in excinfo.value.candidates] == [
        "Mercado Azul",
        "Mercado Verde",
        "Mercado Rosa",
    ]
    assert client.usage.spent == 2


def test_search_is_bounded(api: FakeAPI) -> None:
    for page in range(1, 11):
        api.respond(
            "GET", STORES, stores_page(page, 10, f"Mercado {page}"), params={"page": str(page)}
        )

    with api.client() as client, pytest.raises(errors.AmbiguousStoreError):
        client.stores.find("Mercado")

    assert len(api.requests) == FIND_MAX_PAGES
    assert client.usage.spent == FIND_MAX_PAGES


async def test_async_find_walks_pages_too(api: FakeAPI) -> None:
    api.respond("GET", STORES, stores_page(1, 2, "Mercado Azul"), params={"page": "1"})
    api.respond("GET", STORES, stores_page(2, 2, "Mercado"), params={"page": "2"})

    async with api.async_client() as client:
        found = await client.stores.find("Mercado", state="sp")

    assert found.store_name == "Mercado"
    assert client.usage.spent == 2
