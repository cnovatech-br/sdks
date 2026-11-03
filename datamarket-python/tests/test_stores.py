from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from cnovatech.datamarket import errors, models
from cnovatech.datamarket.resources.stores import select_store

if TYPE_CHECKING:
    from conftest import FakeAPI

STORE_ID = "0f8c7d2e-6b1a-4f3e-9c5d-2a7b8e1f4c63"
COMPETITOR_ID = "7a1d3c5e-9b2f-4e6a-8c0d-1f3b5a7c9e2b"
STORES = "/api/v1/market/stores"
STORE = f"{STORES}/{STORE_ID}"


def store(name: str, store_id: str = STORE_ID) -> models.Store:
    return models.Store(store_id=store_id, store_name=name, state="SP")


def test_list_stores(api: FakeAPI) -> None:
    api.respond("GET", STORES, "listStores.json")

    with api.client() as client:
        page = client.stores.list(search="modelo", state="sp", city="São Paulo")

    assert isinstance(page, models.StoresPage)
    assert page.data[0].store_id == STORE_ID
    assert page.data[0].last_collected_date == datetime.date(2026, 11, 2)
    assert page.data[1].omnichannel is True
    assert api.last_params == {
        "search": "modelo",
        "state": "SP",
        "city": "São Paulo",
        "page": "1",
        "limit": "50",
    }


def test_find_prefers_the_exact_name(api: FakeAPI) -> None:
    api.respond("GET", STORES, "listStores.json")

    with api.client() as client:
        found = client.stores.find("supermercado modelo", state="SP")

    assert found.store_id == STORE_ID
    assert api.last_params == {
        "search": "supermercado modelo",
        "state": "SP",
        "page": "1",
        "limit": "100",
    }
    assert client.usage.spent == 1


def test_find_is_ambiguous_without_an_exact_match(api: FakeAPI) -> None:
    api.respond("GET", STORES, "listStores.json")

    with api.client() as client, pytest.raises(errors.AmbiguousStoreError) as excinfo:
        client.stores.find("Modelo")

    assert excinfo.value.name == "Modelo"
    assert [candidate.store_name for candidate in excinfo.value.candidates] == [
        "Supermercado Modelo",
        "Supermercado Modelo Express",
    ]
    assert "Add state= or city=" in str(excinfo.value)


def test_find_without_results(api: FakeAPI) -> None:
    empty = {
        "data": [],
        "meta": {"page": 1, "limit": 100, "total": 0, "pages": 0},
        "usage": {"query_cost": 1},
    }
    api.respond("GET", STORES, empty)

    with api.client() as client, pytest.raises(errors.StoreNotFoundError) as excinfo:
        client.stores.find("Loja Inexistente")

    assert excinfo.value.code == "store_not_found"
    assert excinfo.value.hint is not None


def test_select_store_accepts_a_single_partial_match() -> None:
    only = store("Supermercado Modelo Express")

    assert select_store("express", [only]) is only


def test_select_store_with_several_exact_matches_is_ambiguous() -> None:
    twins = [store("Mercado Central", "a" * 32), store("mercado central", "b" * 32)]

    with pytest.raises(errors.AmbiguousStoreError) as excinfo:
        select_store("Mercado Central", twins)

    assert excinfo.value.candidates == twins


def test_assortment_costs_two_units_per_block_of_250_rows(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/assortment", "getStoreAssortment.json")

    with api.client() as client:
        page = client.stores.assortment(STORE_ID.upper(), limit=100)

    assert isinstance(page, models.AssortmentPage)
    assert page.store.store_name == "Supermercado Modelo"
    assert page.data[0].wholesale_min_qty == 6
    assert page.data[0].collected_date == datetime.date(2026, 11, 2)
    assert page.page_cost_estimate == 2
    assert page.usage.query_cost == 2
    assert api.last_request.url.path == f"{STORE}/assortment"

    frame = page.to_dataframe()
    assert frame["store_name"].tolist() == ["Supermercado Modelo", "Supermercado Modelo"]
    assert frame["ean"].tolist() == ["7894900011517", "7891991000826"]


def test_assortment_above_the_budget_is_refused_before_sending(api: FakeAPI) -> None:
    with (
        api.client(max_units_per_request=4) as client,
        pytest.raises(errors.BudgetExceededError) as excinfo,
    ):
        client.stores.assortment(STORE_ID, limit=1000)

    assert excinfo.value.estimated_cost == 8
    assert excinfo.value.limit == 4
    assert api.requests == []


def test_store_routes_validate_the_identifier(api: FakeAPI) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="store_id"):
        client.stores.assortment("not-a-uuid")

    assert api.requests == []


def test_unknown_store_is_typed(api: FakeAPI) -> None:
    api.respond(
        "GET",
        f"{STORE}/competitors",
        {
            "error": "not_found",
            "message": "Loja não encontrada. Use um store_id da listagem de lojas.",
        },
        status_code=404,
    )

    with api.client() as client, pytest.raises(errors.StoreNotFoundError) as excinfo:
        client.stores.competitors(STORE_ID)

    assert excinfo.value.status_code == 404
    assert "store_id" in excinfo.value.message


def test_competitors_cost_one_unit_each(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/competitors", "getStoreCompetitors.json")

    with api.client(max_units_per_request=5) as client:
        competitors = client.stores.competitors(STORE_ID, limit=5)

    assert competitors.data[0].store_name == "Mercado Vizinho"
    assert competitors.data[0].overlap_pct == 62.5
    assert competitors.meta.total == 2
    assert api.last_params == {"min_overlap_pct": "10.0", "limit": "5"}

    with api.client(max_units_per_request=5) as client, pytest.raises(errors.BudgetExceededError):
        client.stores.competitors(STORE_ID, limit=6)


def test_competitiveness(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/competitiveness", "getStoreCompetitiveness.json")

    with api.client() as client:
        result = client.stores.competitiveness(STORE_ID, limit=5, market_scope="same_state")

    assert result.summary.competitiveness_score == 57.3
    assert result.data[0].median_price_diff_pct == -2.4
    assert api.last_params == {"min_overlap_pct": "5.0", "limit": "5", "market_scope": "same_state"}


def test_compare_with_a_competitor(api: FakeAPI) -> None:
    api.respond(
        "GET", f"{STORE}/competitors/{COMPETITOR_ID}/products", "getCompetitorProducts.json"
    )

    with api.client() as client:
        page = client.stores.compare(STORE_ID, COMPETITOR_ID, price_position="below", search="coca")

    assert isinstance(page, models.ComparisonPage)
    assert page.competitor.store_name == "Mercado Vizinho"
    assert page.summary.below_count == 3100
    assert page.data[0].price_position == "below"
    assert page.data[1].price_diff_pct is None
    assert page.page_cost_estimate == 2
    assert api.last_params == {
        "price_position": "below",
        "search": "coca",
        "sort_by": "price_diff_pct",
        "sort_order": "desc",
        "page": "1",
        "limit": "50",
    }

    frame = page.to_dataframe()
    assert frame["competitor_store_name"].tolist() == ["Mercado Vizinho", "Mercado Vizinho"]
    assert frame["competitor_price"].tolist() == [9.49, 3.29]


def test_market_position(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/market-position", "getStoreMarketPosition.json")

    with api.client() as client:
        page = client.stores.market_position(STORE_ID, state="sp")

    assert isinstance(page, models.MarketPositionPage)
    assert page.summary.comparable_count == 11900
    assert page.data[0].market.mode_price == 9.49
    assert page.page_cost_estimate == 8
    assert page.usage.query_cost == 8
    assert api.last_params == {"market_scope": "all", "state": "SP", "page": "1", "limit": "1000"}


def test_opportunities(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/opportunities", "getStoreOpportunities.json")

    with api.client() as client:
        page = client.stores.opportunities(STORE_ID, opportunity_type="decrease", min_diff_pct=20)

    assert isinstance(page, models.OpportunitiesPage)
    assert page.data[0].opportunity_type == "decrease"
    assert page.data[0].price_rank == 140
    assert page.summary.increase_count == 1200
    assert api.last_params == {
        "opportunity_type": "decrease",
        "min_diff_pct": "20",
        "max_diff_pct": "100.0",
        "min_store_count": "3",
        "page": "1",
        "limit": "50",
    }


def test_opportunity_type_is_omitted_when_not_given(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/opportunities", "getStoreOpportunities.json")

    with api.client() as client:
        client.stores.opportunities(STORE_ID)

    assert "opportunity_type" not in api.last_params


async def test_async_stores(api: FakeAPI) -> None:
    api.respond("GET", STORES, "listStores.json")
    api.respond("GET", f"{STORE}/market-position", "getStoreMarketPosition.json")

    async with api.async_client() as client:
        found = await client.stores.find("Supermercado Modelo")
        page = await client.stores.market_position(found.store_id, limit=1000)
        items = [item async for item in page.iter_all(max_units=0)]

    assert isinstance(page, models.AsyncMarketPositionPage)
    assert [item.ean for item in items] == ["7894900011517"]
    assert client.usage.spent == 9
