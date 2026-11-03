"""Lookup of a store by name across result pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from conftest import STORES_PATH, stores_page

from cnovatech.datamarket import errors
from cnovatech.datamarket.resources.stores import FIND_MAX_PAGES

if TYPE_CHECKING:
    from conftest import FakeAPI


def test_exact_match_on_a_later_page_is_found(api: FakeAPI) -> None:
    api.respond(
        "GET",
        STORES_PATH,
        stores_page("Mercado Azul", "Mercado Verde", pages=2),
        params={"page": "1"},
    )
    api.respond(
        "GET",
        STORES_PATH,
        stores_page("Mercado", "Mercado Rosa", page=2, pages=2),
        params={"page": "2"},
    )

    with api.client() as client:
        found = client.stores.find("mercado")

    assert found.store_name == "Mercado"
    assert [dict(request.url.params)["page"] for request in api.requests] == ["1", "2"]
    assert client.usage.spent == 2


def test_search_stops_at_the_page_with_the_exact_match(api: FakeAPI) -> None:
    api.respond("GET", STORES_PATH, stores_page("Mercado", "Mercado Verde", pages=3))

    with api.client() as client:
        found = client.stores.find("Mercado")

    assert found.store_name == "Mercado"
    assert len(api.requests) == 1


def test_candidates_from_every_page_are_reported_when_none_is_exact(api: FakeAPI) -> None:
    api.respond(
        "GET",
        STORES_PATH,
        stores_page("Mercado Azul", "Mercado Verde", pages=2),
        params={"page": "1"},
    )
    api.respond(
        "GET", STORES_PATH, stores_page("Mercado Rosa", page=2, pages=2), params={"page": "2"}
    )

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
            "GET",
            STORES_PATH,
            stores_page(f"Mercado {page}", page=page, pages=10),
            params={"page": str(page)},
        )

    with api.client() as client, pytest.raises(errors.AmbiguousStoreError):
        client.stores.find("Mercado")

    assert len(api.requests) == FIND_MAX_PAGES
    assert client.usage.spent == FIND_MAX_PAGES


async def test_async_find_walks_pages_too(api: FakeAPI) -> None:
    api.respond("GET", STORES_PATH, stores_page("Mercado Azul", pages=2), params={"page": "1"})
    api.respond("GET", STORES_PATH, stores_page("Mercado", page=2, pages=2), params={"page": "2"})

    async with api.async_client() as client:
        found = await client.stores.find("Mercado", state="sp")

    assert found.store_name == "Mercado"
    assert client.usage.spent == 2
