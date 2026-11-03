from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from conftest import STORES_PATH, load_fixture, stores_page

from cnovatech.datamarket import errors, models
from cnovatech.datamarket.resources.stores import select_store

if TYPE_CHECKING:
    from conftest import FakeAPI

ASSORTMENT_FIXTURE = load_fixture("getStoreAssortment.json")
COMPARISON_FIXTURE = load_fixture("getCompetitorProducts.json")
STORE_ID = ASSORTMENT_FIXTURE["store"]["store_id"]
STORE_NAME = ASSORTMENT_FIXTURE["store"]["store_name"]
COMPETITOR_ID = COMPARISON_FIXTURE["competitor"]["store_id"]
STORE = f"{STORES_PATH}/{STORE_ID}"


def store(name: str, store_id: str = STORE_ID) -> models.Store:
    return models.Store(store_id=store_id, store_name=name, state="SP")


def test_list_stores(api: FakeAPI) -> None:
    expected = load_fixture("listStores.json")
    api.respond("GET", STORES_PATH, expected)

    with api.client() as client:
        page = client.stores.list(search="max", state="pr", city="Quedas do Iguacu", limit=5)

    assert isinstance(page, models.StoresPage)
    assert page.data[0].store_id == expected["data"][0]["store_id"]
    assert page.data[0].last_collected_date == datetime.date.fromisoformat(
        expected["data"][0]["last_collected_date"]
    )
    assert page.meta.total == expected["meta"]["total"]
    assert api.last_params == {
        "search": "max",
        "state": "PR",
        "city": "Quedas do Iguacu",
        "page": "1",
        "limit": "5",
    }


def test_find_prefers_the_exact_name(api: FakeAPI) -> None:
    api.respond(
        "GET", STORES_PATH, stores_page("Supermercado Modelo", "Supermercado Modelo Express")
    )

    with api.client() as client:
        found = client.stores.find("supermercado modelo", state="SP")

    assert found.store_name == "Supermercado Modelo"
    assert api.last_params == {
        "search": "supermercado modelo",
        "state": "SP",
        "page": "1",
        "limit": "100",
    }
    assert client.usage.spent == 1


def test_find_is_ambiguous_without_an_exact_match(api: FakeAPI) -> None:
    api.respond(
        "GET", STORES_PATH, stores_page("Supermercado Modelo", "Supermercado Modelo Express")
    )

    with api.client() as client, pytest.raises(errors.AmbiguousStoreError) as excinfo:
        client.stores.find("Modelo")

    assert excinfo.value.name == "Modelo"
    assert [candidate.store_name for candidate in excinfo.value.candidates] == [
        "Supermercado Modelo",
        "Supermercado Modelo Express",
    ]
    assert "Add state= or city=" in str(excinfo.value)


def test_find_without_results(api: FakeAPI) -> None:
    api.respond("GET", STORES_PATH, stores_page())

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
    api.respond("GET", f"{STORE}/assortment", ASSORTMENT_FIXTURE)

    with api.client() as client:
        page = client.stores.assortment(STORE_ID.upper(), limit=5)

    assert isinstance(page, models.AssortmentPage)
    assert page.store.store_name == STORE_NAME
    assert page.data[0].collected_date == datetime.date.fromisoformat(
        ASSORTMENT_FIXTURE["data"][0]["collected_date"]
    )
    assert page.page_cost_estimate == 2
    assert page.usage.query_cost == 2
    assert page.estimate_remaining_cost() == (ASSORTMENT_FIXTURE["meta"]["pages"] - 1) * 2
    assert api.last_request.url.path == f"{STORE}/assortment"

    frame = page.to_dataframe()
    assert set(frame["store_name"]) == {STORE_NAME}
    assert frame["ean"].tolist() == [item["ean"] for item in ASSORTMENT_FIXTURE["data"]]


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
    expected = load_fixture("getStoreCompetitors.json")
    api.respond("GET", f"{STORE}/competitors", expected)

    with api.client(max_units_per_request=2) as client:
        competitors = client.stores.competitors(STORE_ID, limit=2)

    assert competitors.data[0].store_name == expected["data"][0]["store_name"]
    assert competitors.data[0].overlap_pct == expected["data"][0]["overlap_pct"]
    assert competitors.meta.total == expected["meta"]["total"]
    assert competitors.usage.query_cost == 2
    assert api.last_params == {"min_overlap_pct": "10.0", "limit": "2"}

    with (
        api.client(max_units_per_request=2) as client,
        pytest.raises(errors.BudgetExceededError),
    ):
        client.stores.competitors(STORE_ID, limit=3)


def test_competitiveness(api: FakeAPI) -> None:
    expected = load_fixture("getStoreCompetitiveness.json")
    api.respond("GET", f"{STORE}/competitiveness", expected)

    with api.client() as client:
        result = client.stores.competitiveness(STORE_ID, limit=2, market_scope="same_state")

    assert result.summary.competitiveness_score == expected["summary"]["competitiveness_score"]
    assert result.data[0].below_pct == expected["data"][0]["below_pct"]
    assert api.last_params == {"min_overlap_pct": "5.0", "limit": "2", "market_scope": "same_state"}


def test_compare_with_a_competitor(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/competitors/{COMPETITOR_ID}/products", COMPARISON_FIXTURE)

    with api.client() as client:
        page = client.stores.compare(
            STORE_ID, COMPETITOR_ID, price_position="above", search="kleenex", limit=5
        )

    assert isinstance(page, models.ComparisonPage)
    assert page.competitor.store_name == COMPARISON_FIXTURE["competitor"]["store_name"]
    assert page.summary.below_count == COMPARISON_FIXTURE["summary"]["below_count"]
    assert page.data[0].price_position == COMPARISON_FIXTURE["data"][0]["price_position"]
    assert page.page_cost_estimate == 2
    assert api.last_params == {
        "price_position": "above",
        "search": "kleenex",
        "sort_by": "price_diff_pct",
        "sort_order": "desc",
        "page": "1",
        "limit": "5",
    }

    frame = page.to_dataframe()
    assert set(frame["competitor_store_name"]) == {COMPARISON_FIXTURE["competitor"]["store_name"]}
    assert frame["competitor_price"].tolist() == [
        item["competitor_price"] for item in COMPARISON_FIXTURE["data"]
    ]


def test_market_position(api: FakeAPI) -> None:
    expected = load_fixture("getStoreMarketPosition.json")
    api.respond("GET", f"{STORE}/market-position", expected)

    with api.client() as client:
        page = client.stores.market_position(STORE_ID, state="pr", limit=5)

    assert isinstance(page, models.MarketPositionPage)
    assert page.summary.comparable_count == expected["summary"]["comparable_count"]
    assert page.data[0].market.mode_price == expected["data"][0]["market"]["mode_price"]
    assert page.page_cost_estimate == 2
    assert api.last_params == {"market_scope": "all", "state": "PR", "page": "1", "limit": "5"}


def test_market_position_default_page_costs_eight_units(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/market-position", load_fixture("getStoreMarketPosition.json"))

    with api.client() as client:
        page = client.stores.market_position(STORE_ID)

    assert page.page_cost_estimate == 8
    assert api.last_params["limit"] == "1000"


def test_opportunities(api: FakeAPI) -> None:
    expected = load_fixture("getStoreOpportunities.json")
    api.respond("GET", f"{STORE}/opportunities", expected)

    with api.client() as client:
        page = client.stores.opportunities(
            STORE_ID, opportunity_type="increase", min_diff_pct=20, limit=5
        )

    assert isinstance(page, models.OpportunitiesPage)
    assert page.data[0].opportunity_type == expected["data"][0]["opportunity_type"]
    assert page.data[0].price_rank == expected["data"][0]["price_rank"]
    assert page.summary.increase_count == expected["summary"]["increase_count"]
    assert api.last_params == {
        "opportunity_type": "increase",
        "min_diff_pct": "20",
        "max_diff_pct": "100.0",
        "min_store_count": "3",
        "page": "1",
        "limit": "5",
    }


def test_opportunity_type_is_omitted_when_not_given(api: FakeAPI) -> None:
    api.respond("GET", f"{STORE}/opportunities", load_fixture("getStoreOpportunities.json"))

    with api.client() as client:
        client.stores.opportunities(STORE_ID)

    assert "opportunity_type" not in api.last_params


async def test_async_stores(api: FakeAPI) -> None:
    api.respond("GET", STORES_PATH, stores_page(STORE_NAME))
    api.respond("GET", f"{STORE}/market-position", load_fixture("getStoreMarketPosition.json"))

    async with api.async_client() as client:
        found = await client.stores.find(STORE_NAME)
        page = await client.stores.market_position(STORE_ID, limit=5)
        items = [item async for item in page.iter_all(max_pages=0)]

    assert found.store_name == STORE_NAME
    assert isinstance(page, models.AsyncMarketPositionPage)
    assert len(items) == len(page.data)
    assert client.usage.spent == 3
