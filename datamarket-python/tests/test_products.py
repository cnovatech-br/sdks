from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

import pytest
from conftest import load_fixture

from cnovatech.datamarket import errors, models

if TYPE_CHECKING:
    from conftest import FakeAPI

CATALOG = "/api/v1/market/products/catalog"
PRODUCT_FIXTURE = load_fixture("getProductByEan.json")
EAN = PRODUCT_FIXTURE["ean"]
PRODUCT = f"/api/v1/market/products/ean/{EAN}"


def test_catalog_sends_filters_and_returns_a_page(api: FakeAPI) -> None:
    expected = load_fixture("getCatalog.json")
    api.respond("GET", CATALOG, expected)

    with api.client() as client:
        page = client.products.catalog(search="coca cola 2l", state="sp", min_price=5, limit=5)

    assert isinstance(page, models.CatalogPage)
    assert [product.ean for product in page] == [item["ean"] for item in expected["data"]]
    assert page.data[0].median_price == expected["data"][0]["median_price"]
    assert page.meta.pages == expected["meta"]["pages"]
    assert page.has_next is True
    assert page.estimate_remaining_cost() == expected["meta"]["pages"] - 1
    assert page.usage.query_cost == 1
    assert client.usage.spent == 1
    assert api.last_params == {
        "search": "coca cola 2l",
        "state": "SP",
        "min_price": "5",
        "page": "1",
        "limit": "5",
    }
    assert api.last_request.headers["X-API-Key"] == "dm_test_key"
    assert page.request_info is not None
    assert page.request_info.path == CATALOG


def test_catalog_pages_are_walked_without_refetching_the_first(api: FakeAPI) -> None:
    fixture = load_fixture("getCatalog.json")
    first: dict[str, Any] = {**fixture, "meta": {"page": 1, "limit": 1, "total": 2, "pages": 2}}
    first["data"] = [fixture["data"][0]]
    second: dict[str, Any] = {**first, "meta": {"page": 2, "limit": 1, "total": 2, "pages": 2}}
    second["data"] = [fixture["data"][1]]
    api.respond("GET", CATALOG, first, params={"page": "1"})
    api.respond("GET", CATALOG, second, params={"page": "2"})

    with api.client() as client:
        page = client.products.catalog(brand="COCA-COLA", limit=1)
        assert page.estimate_remaining_cost() == 1
        eans = [product.ean for product in page.iter_all(max_units=1)]

    assert eans == [fixture["data"][0]["ean"], fixture["data"][1]["ean"]]
    assert [dict(request.url.params)["page"] for request in api.requests] == ["1", "2"]
    assert client.usage.spent == 2


def test_catalog_without_filter_beyond_page_20(api: FakeAPI) -> None:
    api.respond("GET", CATALOG, "error_filter_required.json", status_code=400)

    with api.client() as client, pytest.raises(errors.FilterRequiredError) as excinfo:
        client.products.catalog(page=21)

    assert excinfo.value.code == "filter_required"
    assert excinfo.value.hint is not None
    assert client.usage.spent == 0


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"limit": 101}, "limit must be an integer between 1 and 100"),
        ({"page": 0}, "page must be an integer"),
        ({"state": "SAO"}, "two-letter state code"),
    ],
)
def test_catalog_rejects_invalid_arguments_before_sending(
    api: FakeAPI, arguments: dict[str, Any], message: str
) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match=message):
        client.products.catalog(**arguments)

    assert api.requests == []


def test_departments(api: FakeAPI) -> None:
    expected = load_fixture("listDepartments.json")
    api.respond("GET", "/api/v1/market/products/departments", expected)

    with api.client() as client:
        departments = client.products.departments()

    assert departments.summary.category_count == expected["summary"]["category_count"]
    assert departments.data[0].department == expected["data"][0]["department"]
    assert (
        departments.data[0].categories[0].category
        == (expected["data"][0]["categories"][0]["category"])
    )
    assert departments.to_dataframe()["department"].tolist() == [
        item["department"] for item in expected["data"]
    ]


def test_brands(api: FakeAPI) -> None:
    expected = load_fixture("listBrands.json")
    api.respond("GET", "/api/v1/market/products/brands", expected)

    with api.client() as client:
        page = client.products.brands(search="coca", department="BEBIDAS", limit=5)

    assert isinstance(page, models.BrandsPage)
    assert [brand.brand for brand in page] == [item["brand"] for item in expected["data"]]
    assert page.data[0].categories == expected["data"][0]["categories"]
    assert api.last_params == {"search": "coca", "department": "BEBIDAS", "page": "1", "limit": "5"}


def test_products_by_brand(api: FakeAPI) -> None:
    expected = load_fixture("getProductsByBrand.json")
    api.respond("GET", "/api/v1/market/products/by-brand", expected)

    with api.client() as client:
        page = client.products.by_brand("COCA-COLA", category="REFRIGERANTES", limit=5)

    assert isinstance(page, models.ProductsByBrandPage)
    assert page.data[0].price_cv_pct == expected["data"][0]["price_cv_pct"]
    assert api.last_params == {
        "brand": "COCA-COLA",
        "category": "REFRIGERANTES",
        "page": "1",
        "limit": "5",
    }


def test_get_product_by_ean(api: FakeAPI) -> None:
    api.respond("GET", PRODUCT, PRODUCT_FIXTURE)
    first_offer = PRODUCT_FIXTURE["offers"][0]

    with api.client() as client:
        product = client.products.get(f" {EAN} ", state="sp", sort_by="store_name")

    assert isinstance(product, models.Product)
    assert product.market.median_price == PRODUCT_FIXTURE["market"]["median_price"]
    assert product.offers[0].store_name == first_offer["store_name"]
    assert product.offers[0].collected_at == datetime.datetime.fromisoformat(
        first_offer["collected_at"]
    )
    assert product.usage.query_cost == 1
    assert api.last_params == {"state": "SP", "sort_by": "store_name", "sort_order": "asc"}

    frame = product.to_dataframe()
    assert len(frame) == len(PRODUCT_FIXTURE["offers"])
    assert set(frame["market_median_price"]) == {PRODUCT_FIXTURE["market"]["median_price"]}
    assert frame["price"].tolist() == [offer["price"] for offer in PRODUCT_FIXTURE["offers"]]


def test_get_sends_the_city_and_channel_filters(api: FakeAPI) -> None:
    api.respond("GET", PRODUCT, PRODUCT_FIXTURE)

    with api.client() as client:
        client.products.get(EAN, city="Campinas", channel="delivery", sort_order="desc")

    assert api.last_params == {
        "city": "Campinas",
        "channel": "delivery",
        "sort_by": "price",
        "sort_order": "desc",
    }


def test_get_rejects_a_malformed_ean_before_sending(api: FakeAPI) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="ean"):
        client.products.get("7894900011")

    assert api.requests == []


def test_get_unknown_ean_is_typed_and_not_billed(api: FakeAPI) -> None:
    api.respond(
        "GET",
        "/api/v1/market/products/ean/0000000000000",
        "error_ean_not_found.json",
        status_code=404,
    )

    with api.client() as client, pytest.raises(errors.EANNotFoundError) as excinfo:
        client.products.get("0000000000000")

    assert excinfo.value.ean == "0000000000000"
    assert excinfo.value.hint is not None
    assert "coverage" in excinfo.value.hint
    assert isinstance(excinfo.value, errors.NotFoundError)
    assert client.usage.spent == 0


def test_price_history(api: FakeAPI) -> None:
    expected = load_fixture("getProductPriceHistory.json")
    api.respond("GET", f"{PRODUCT}/price-history", expected)

    with api.client() as client:
        history = client.products.price_history(
            EAN, days=7, granularity="daily", state="PR", store_limit=3
        )

    assert history.period_days == expected["period_days"]
    assert history.market_series[0].date == datetime.date.fromisoformat(
        expected["market_series"][0]["date"]
    )
    assert (
        history.store_series[0].points[0].price == expected["store_series"][0]["points"][0]["price"]
    )
    assert api.last_params == {
        "days": "7",
        "granularity": "daily",
        "state": "PR",
        "store_limit": "3",
    }

    market = history.to_dataframe()
    assert market["median_price"].tolist() == [
        bucket["median_price"] for bucket in expected["market_series"]
    ]
    assert set(market["ean"]) == {EAN}

    stores = history.to_dataframe(series="stores")
    assert len(stores) == sum(len(series["points"]) for series in expected["store_series"])
    assert stores["store_name"].iloc[0] == expected["store_series"][0]["store_name"]
    assert "points" not in stores.columns


def test_price_history_out_of_range_is_a_typed_validation_error(api: FakeAPI) -> None:
    """The API validates value ranges itself; its 422 names the field and the rule."""
    api.respond("GET", f"{PRODUCT}/price-history", "error_validation_error.json", status_code=422)

    with api.client() as client, pytest.raises(errors.UnprocessableEntityError) as excinfo:
        client.products.price_history(EAN, days=400)

    assert excinfo.value.code == "validation_error"
    assert excinfo.value.details == [
        errors.FieldError(
            field="query -> days",
            message="Input should be less than or equal to 180",
            type="less_than_equal",
        )
    ]
    assert client.usage.spent == 0


def test_coverage_accepts_any_iterable_of_codes(api: FakeAPI) -> None:
    api.respond("POST", "/api/v1/market/products/coverage", "checkCatalogCoverage.json")

    with api.client() as client:
        client.products.coverage(code for code in (EAN, "0000000000000"))

    assert api.last_request.read() == f'{{"eans":["{EAN}","0000000000000"]}}'.encode()


def test_coverage_posts_the_codes(api: FakeAPI) -> None:
    expected = load_fixture("checkCatalogCoverage.json")
    api.respond("POST", "/api/v1/market/products/coverage", expected)

    with api.client() as client:
        coverage = client.products.coverage([f" {EAN}", "0000000000000"])

    assert coverage.summary.coverage_pct == expected["summary"]["coverage_pct"]
    assert [item.found for item in coverage.data] == [item["found"] for item in expected["data"]]
    assert api.last_request.method == "POST"
    assert api.last_request.headers["Content-Type"] == "application/json"
    assert api.last_request.read() == f'{{"eans":["{EAN}","0000000000000"]}}'.encode()


def test_coverage_estimates_its_cost_and_honours_the_budget(api: FakeAPI) -> None:
    codes = [f"{7890000000000 + index:013d}" for index in range(300)]

    with (
        api.client(max_units_per_request=1) as client,
        pytest.raises(errors.BudgetExceededError) as excinfo,
    ):
        client.products.coverage(codes)

    assert excinfo.value.estimated_cost == 2
    assert api.requests == []


def test_coverage_rejects_more_than_500_codes(api: FakeAPI) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="at most 500"):
        client.products.coverage([EAN] * 501)


async def test_async_products_share_the_same_operations(api: FakeAPI) -> None:
    catalog = load_fixture("getCatalog.json")
    api.respond("GET", PRODUCT, PRODUCT_FIXTURE)
    api.respond("GET", CATALOG, catalog)

    async with api.async_client() as client:
        product = await client.products.get(EAN)
        page = await client.products.catalog(search="coca", limit=5)
        eans = [item.ean async for item in page.iter_all(max_pages=0)]

    assert product.product_name == PRODUCT_FIXTURE["product_name"]
    assert isinstance(page, models.AsyncCatalogPage)
    assert eans == [item["ean"] for item in catalog["data"]]
    assert client.usage.spent == 2
