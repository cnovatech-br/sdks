"""Trend endpoints: rankings, per-product detail and per-store lists.

The rankings say which products changed price, went on promotion or went out
of stock; the detail says what happened to one of them, store by store; the
store lists say what one store is promoting and what is missing from it.
"""

from __future__ import annotations

import datetime
import json
import re
from typing import TYPE_CHECKING, Any

import pytest
from conftest import load_fixture

from cnovatech.datamarket import errors, models

if TYPE_CHECKING:
    from conftest import FakeAPI

PRODUCTS = "/api/v1/market/products"
EAN = load_fixture("getProductPriceChanges.json")["ean"]
STORE_ID = load_fixture("getStoreStockouts.json")["store"]["store_id"]
STORE = f"/api/v1/market/stores/{STORE_ID}"
HOUR = re.compile(r"\d{2}:\d{2}:\d{2}")


# --- rankings -----------------------------------------------------------------


def test_price_changes_sends_filters_and_returns_a_page(api: FakeAPI) -> None:
    expected = load_fixture("getPriceChanges.json")
    api.respond("GET", f"{PRODUCTS}/price-changes", expected)

    with api.client() as client:
        page = client.products.price_changes(brand="COCA-COLA", state="sp", days=90, limit=5)

    assert isinstance(page, models.PriceChangesPage)
    assert [row.ean for row in page] == [item["ean"] for item in expected["data"]]
    first = page.data[0]
    assert first.repriced_store_count <= first.store_count
    assert first.price_increase_store_count + first.price_decrease_store_count <= (
        first.repriced_store_count
    )
    assert page.period_days == expected["period_days"]
    assert page.summary.product_count == expected["meta"]["total"]
    assert isinstance(page.summary.last_collected_at, datetime.datetime)
    assert page.usage.query_cost == 1
    assert api.last_params == {
        "days": "90",
        "brand": "COCA-COLA",
        "state": "SP",
        "min_store_count": "5",
        "sort_by": "repriced_store_pct",
        "sort_order": "desc",
        "page": "1",
        "limit": "5",
    }


def test_promotions_can_ask_for_a_minimum_discount(api: FakeAPI) -> None:
    expected = load_fixture("getPromotions.json")
    api.respond("GET", f"{PRODUCTS}/promotions", expected)

    with api.client() as client:
        page = client.products.promotions(
            category="REFRIGERANTES", min_discount_pct=20, sort_by="median_discount_pct"
        )

    assert isinstance(page, models.PromotionsPage)
    assert page.data[0].promo_store_count <= page.data[0].store_count
    assert api.last_params["min_discount_pct"] == "20"
    assert api.last_params["sort_by"] == "median_discount_pct"
    assert api.last_params["days"] == "30"


def test_stockouts_ranking_is_ordered_by_share_of_stores_by_default(api: FakeAPI) -> None:
    expected = load_fixture("getStockouts.json")
    api.respond("GET", f"{PRODUCTS}/stockouts", expected)

    with api.client() as client:
        page = client.products.stockouts(brand="NESTLE", min_store_count=10)

    assert isinstance(page, models.StockoutsPage)
    shares = [row.stockout_store_pct for row in page]
    assert shares == sorted(shares, reverse=True)
    assert all(1 <= row.stockout_store_count <= row.store_count for row in page)
    assert api.last_params["sort_by"] == "stockout_store_pct"
    assert api.last_params["min_store_count"] == "10"


def test_ranking_pages_are_walked(api: FakeAPI) -> None:
    fixture = load_fixture("getStockouts.json")
    first: dict[str, Any] = {**fixture, "meta": {"page": 1, "limit": 1, "total": 2, "pages": 2}}
    first["data"] = [fixture["data"][0]]
    second: dict[str, Any] = {**first, "meta": {"page": 2, "limit": 1, "total": 2, "pages": 2}}
    second["data"] = [fixture["data"][1]]
    api.respond("GET", f"{PRODUCTS}/stockouts", first, params={"page": "1"})
    api.respond("GET", f"{PRODUCTS}/stockouts", second, params={"page": "2"})

    with api.client() as client:
        page = client.products.stockouts(brand="NESTLE", limit=1)
        eans = [row.ean for row in page.iter_all(max_units=1)]

    assert eans == [fixture["data"][0]["ean"], fixture["data"][1]["ean"]]
    assert client.usage.spent == 2


@pytest.mark.parametrize("method", ["price_changes", "promotions", "stockouts"])
@pytest.mark.parametrize("days", [0, 7, 60, 180, True])
def test_only_the_windows_the_api_keeps_are_sent(api: FakeAPI, method: str, days: int) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="30 or 90"):
        getattr(client.products, method)(days=days)

    assert api.requests == []


def test_a_ranking_page_is_capped_at_100_rows(api: FakeAPI) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="limit"):
        client.products.promotions(limit=101)

    assert api.requests == []


# --- one product, store by store ----------------------------------------------


def test_price_change_detail_returns_the_events_of_each_store(api: FakeAPI) -> None:
    expected = load_fixture("getProductPriceChanges.json")
    api.respond("GET", f"{PRODUCTS}/ean/{EAN}/price-changes", expected)

    with api.client() as client:
        page = client.products.price_change_detail(EAN, state="sp", min_price_change_count=1)

    assert isinstance(page, models.ProductPriceChangesPage)
    assert page.ean == EAN
    assert page.product_name == expected["product_name"]
    assert page.summary.repriced_store_count <= page.summary.store_count
    assert page.by_state[0].state == expected["by_state"][0]["state"]
    store = page.data[0]
    assert store.price_change_count == len(expected["data"][0]["changes"]) or (
        store.price_change_count >= len(store.changes)
    )
    change = store.changes[0]
    # An event carries a calendar day, never the hour of a collection.
    assert type(change.change_date) is datetime.date
    assert change.previous_price != change.price
    assert type(store.last_collected_date) is datetime.date
    assert api.last_params == {
        "days": "30",
        "state": "SP",
        "min_price_change_count": "1",
        "page": "1",
        "limit": "100",
    }


def test_promotion_detail_carries_periods_and_the_series_by_day(api: FakeAPI) -> None:
    expected = load_fixture("getProductPromotions.json")
    api.respond("GET", f"{PRODUCTS}/ean/{EAN}/promotions", expected)

    with api.client() as client:
        page = client.products.promotion_detail(EAN, on_promotion=True, days=90)

    assert isinstance(page, models.ProductPromotionsPage)
    assert api.last_params["on_promotion"] == "true"
    assert api.last_params["days"] == "90"
    store = page.data[0]
    assert store.list_price > store.price
    period = store.periods[0]
    assert period.start_date <= period.end_date
    assert page.by_day[0].promo_store_count <= page.by_day[0].store_count
    assert page.summary.promo_store_count <= page.summary.store_count


def test_stockout_detail_says_since_when(api: FakeAPI) -> None:
    expected = load_fixture("getProductStockouts.json")
    api.respond("GET", f"{PRODUCTS}/ean/{EAN}/stockouts", expected)

    with api.client() as client:
        page = client.products.stockout_detail(EAN, available=False)

    assert isinstance(page, models.ProductStockoutsPage)
    assert api.last_params["available"] == "false"
    assert page.summary.stockout_store_count <= page.summary.store_count
    assert page.summary.never_available_store_count >= 0
    for store in page:
        # Out of stock means a start date; available means none.
        assert (store.unavailable_since_date is None) == store.available
        assert store.unavailable_day_count == sum(period.day_count for period in store.periods)


def test_a_filter_left_unset_is_not_sent(api: FakeAPI) -> None:
    api.respond("GET", f"{PRODUCTS}/ean/{EAN}/stockouts", "getProductStockouts.json")

    with api.client() as client:
        client.products.stockout_detail(EAN)

    assert "available" not in api.last_params
    assert "state" not in api.last_params


@pytest.mark.parametrize("method", ["price_change_detail", "promotion_detail", "stockout_detail"])
def test_detail_validates_the_ean_and_the_window_before_sending(api: FakeAPI, method: str) -> None:
    with api.client() as client:
        with pytest.raises(errors.InvalidRequestError, match="ean"):
            getattr(client.products, method)("not-an-ean")
        with pytest.raises(errors.InvalidRequestError, match="30 or 90"):
            getattr(client.products, method)(EAN, days=60)
        with pytest.raises(errors.InvalidRequestError, match="limit"):
            getattr(client.products, method)(EAN, limit=301)

    assert api.requests == []


def test_detail_of_an_unknown_ean_is_typed_and_free(api: FakeAPI) -> None:
    api.respond(
        "GET", f"{PRODUCTS}/ean/{EAN}/stockouts", "error_ean_not_found.json", status_code=404
    )

    with api.client() as client, pytest.raises(errors.EANNotFoundError):
        client.products.stockout_detail(EAN)

    assert client.usage.spent == 0


# --- one store, product by product --------------------------------------------


def test_store_stockouts_keeps_the_market_next_to_each_product(api: FakeAPI) -> None:
    expected = load_fixture("getStoreStockouts.json")
    api.respond("GET", f"{STORE}/stockouts", expected)

    with api.client() as client:
        page = client.stores.stockouts(STORE_ID, available=False, brand="NESTLE", limit=5)

    assert isinstance(page, models.StoreStockoutsPage)
    assert page.store.store_id == STORE_ID
    assert page.summary.stockout_count <= page.summary.sold_product_count
    row = page.data[0]
    assert row.market.stockout_store_count <= row.market.store_count
    assert page.usage.query_cost == 2
    assert api.last_params == {
        "days": "30",
        "available": "false",
        "brand": "NESTLE",
        "sort_by": "store_count",
        "sort_order": "desc",
        "page": "1",
        "limit": "5",
    }


def test_store_promotions_flags_a_list_price_nobody_was_charged(api: FakeAPI) -> None:
    expected = load_fixture("getStorePromotions.json")
    api.respond("GET", f"{STORE}/promotions", expected)

    with api.client() as client:
        page = client.stores.promotions(STORE_ID, on_promotion=True, min_discount_pct=20)

    assert isinstance(page, models.StorePromotionsPage)
    assert api.last_params["on_promotion"] == "true"
    assert api.last_params["min_discount_pct"] == "20"
    summary = page.summary
    assert summary.on_promotion_count + summary.ended_promotion_count == (
        summary.promo_product_count
    )
    row = page.data[0]
    assert isinstance(row.always_on_promotion, bool)
    assert row.list_price > row.price
    assert row.market.promo_store_count <= row.market.store_count


@pytest.mark.parametrize("name", ["getStoreStockouts", "getStorePromotions"])
def test_store_lists_carry_days_and_no_product_page(name: str) -> None:
    """Whole-store answers never carry an hour of collection or a product link."""
    rows = json.dumps(load_fixture(f"{name}.json")["data"])

    assert "product_url" not in rows
    assert not HOUR.search(rows)


@pytest.mark.parametrize("method", ["stockouts", "promotions"])
def test_store_lists_cost_two_units_per_block_of_250_rows(api: FakeAPI, method: str) -> None:
    with (
        api.client(max_units_per_request=1) as client,
        pytest.raises(errors.BudgetExceededError) as excinfo,
    ):
        getattr(client.stores, method)(STORE_ID, limit=200)

    assert excinfo.value.estimated_cost == 2
    assert api.requests == []


@pytest.mark.parametrize("method", ["stockouts", "promotions"])
def test_store_lists_of_an_unknown_store(api: FakeAPI, method: str) -> None:
    api.respond(
        "GET",
        f"{STORE}/{method}",
        {"error": "not_found", "message": "Loja não encontrada. Use um store_id da listagem."},
        status_code=404,
    )

    with api.client() as client, pytest.raises(errors.StoreNotFoundError):
        getattr(client.stores, method)(STORE_ID)


@pytest.mark.parametrize("method", ["stockouts", "promotions"])
def test_store_lists_cap_the_page_at_200_rows(api: FakeAPI, method: str) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="limit"):
        getattr(client.stores, method)(STORE_ID, limit=201)

    assert api.requests == []


# --- catalogue ordering -------------------------------------------------------


def test_catalog_can_rank_by_the_stores_of_one_state(api: FakeAPI) -> None:
    fixture = load_fixture("getCatalog.json")
    payload = {**fixture, "data": [{**fixture["data"][0], "state_store_count": 27}]}
    api.respond("GET", f"{PRODUCTS}/catalog", payload)

    with api.client() as client:
        page = client.products.catalog(
            state="sc", sort_by="state_store_count", min_store_count=50, limit=5
        )

    assert page.data[0].state_store_count == 27
    assert api.last_params == {
        "state": "SC",
        "min_store_count": "50",
        "sort_by": "state_store_count",
        "sort_order": "desc",
        "page": "1",
        "limit": "5",
    }


def test_catalog_sends_no_ordering_by_default(api: FakeAPI) -> None:
    api.respond("GET", f"{PRODUCTS}/catalog", "getCatalog.json")

    with api.client() as client:
        page = client.products.catalog(search="coca cola 2l", limit=5)

    assert "sort_by" not in api.last_params
    assert "sort_order" not in api.last_params
    # Production does not send the field yet; the model keeps it optional.
    assert page.data[0].state_store_count is None


# --- asynchronous client ------------------------------------------------------


async def test_async_trends_share_the_same_operations(api: FakeAPI) -> None:
    api.respond("GET", f"{PRODUCTS}/stockouts", "getStockouts.json")
    api.respond("GET", f"{PRODUCTS}/ean/{EAN}/price-changes", "getProductPriceChanges.json")
    api.respond("GET", f"{STORE}/promotions", "getStorePromotions.json")

    async with api.async_client() as client:
        ranking = await client.products.stockouts(brand="NESTLE")
        detail = await client.products.price_change_detail(EAN, min_price_change_count=1)
        store = await client.stores.promotions(STORE_ID, on_promotion=True)

    assert isinstance(ranking, models.AsyncStockoutsPage)
    assert isinstance(detail, models.AsyncProductPriceChangesPage)
    assert isinstance(store, models.AsyncStorePromotionsPage)
    assert detail.data[0].changes[0].change_date <= detail.data[0].last_collected_date
    assert client.usage.spent == 1 + 1 + 2
