from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

import pytest

from cnovatech.datamarket import errors, models

if TYPE_CHECKING:
    from conftest import FakeAPI

CATALOG = "/api/v1/market/products/catalog"
PRODUCT = "/api/v1/market/products/ean/7894900011517"


def test_catalog_sends_filters_and_returns_a_page(api: FakeAPI) -> None:
    api.respond("GET", CATALOG, "getCatalog.json")

    with api.client() as client:
        page = client.products.catalog(search="coca cola 2l", state="sp", min_price=5, limit=50)

    assert isinstance(page, models.CatalogPage)
    assert page.data[0].ean == "7894900011517"
    assert page.data[0].median_price == 9.49
    assert page.meta.pages == 1
    assert page.usage.query_cost == 1
    assert page.has_next is False
    assert page.estimate_remaining_cost() == 0
    assert client.usage.spent == 1
    assert api.last_params == {
        "search": "coca cola 2l",
        "state": "SP",
        "min_price": "5",
        "page": "1",
        "limit": "50",
    }
    assert api.last_request.headers["X-API-Key"] == "dm_test_key"
    assert page.request_info is not None
    assert page.request_info.path == CATALOG


def test_catalog_pages_are_walked_without_refetching_the_first(api: FakeAPI) -> None:
    first = {
        **api_fixture("getCatalog.json"),
        "meta": {"page": 1, "limit": 1, "total": 2, "pages": 2},
    }
    second = {**first, "meta": {"page": 2, "limit": 1, "total": 2, "pages": 2}}
    second["data"] = [first["data"][1]]
    api.respond("GET", CATALOG, first, params={"page": "1"})
    api.respond("GET", CATALOG, second, params={"page": "2"})

    with api.client() as client:
        page = client.products.catalog(brand="COCA-COLA", limit=1)
        assert page.estimate_remaining_cost() == 1
        eans = [product.ean for product in page.iter_all(max_units=1)]

    assert eans == ["7894900011517", "7894900027013", "7894900027013"]
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
    api.respond("GET", "/api/v1/market/products/departments", "listDepartments.json")

    with api.client() as client:
        departments = client.products.departments()

    assert departments.summary.category_count == 3
    assert departments.data[0].department == "Bebidas"
    assert departments.data[0].categories[1].category == "Cervejas"
    assert departments.to_dataframe()["department"].tolist() == ["Bebidas", "Mercearia"]


def test_brands(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/market/products/brands", "listBrands.json")

    with api.client() as client:
        page = client.products.brands(search="coca", department="Bebidas")

    assert isinstance(page, models.BrandsPage)
    assert [brand.brand for brand in page] == ["COCA-COLA", "GALLO"]
    assert page.data[0].categories == ["Refrigerantes", "Sucos", "Águas"]
    assert api.last_params == {
        "search": "coca",
        "department": "Bebidas",
        "page": "1",
        "limit": "50",
    }


def test_products_by_brand(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/market/products/by-brand", "getProductsByBrand.json")

    with api.client() as client:
        page = client.products.by_brand("COCA-COLA", category="Refrigerantes", limit=100)

    assert isinstance(page, models.ProductsByBrandPage)
    assert page.data[0].price_cv_pct == 11.2
    assert api.last_params == {
        "brand": "COCA-COLA",
        "category": "Refrigerantes",
        "page": "1",
        "limit": "100",
    }


def test_get_product_by_ean(api: FakeAPI) -> None:
    api.respond("GET", PRODUCT, "getProductByEan.json")

    with api.client() as client:
        product = client.products.get(" 7894900011517 ", state="sp", sort_by="store_name")

    assert isinstance(product, models.Product)
    assert product.market.median_price == 9.49
    assert product.offers[0].store_name == "Supermercado Modelo"
    assert product.offers[0].collected_at == datetime.datetime(
        2026, 11, 2, 6, 12, 44, tzinfo=datetime.timezone(datetime.timedelta(hours=-3))
    )
    assert product.offers[1].available is False
    assert product.usage.remaining == 995
    assert api.last_params == {"state": "SP", "sort_by": "store_name", "sort_order": "asc"}

    frame = product.to_dataframe()
    assert len(frame) == 2
    assert frame["market_median_price"].tolist() == [9.49, 9.49]
    assert frame["price"].tolist() == [8.99, 9.49]


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
    api.respond("GET", f"{PRODUCT}/price-history", "getProductPriceHistory.json")

    with api.client() as client:
        history = client.products.price_history(
            "7894900011517", days=30, granularity="weekly", state="SP", store_limit=10
        )

    assert history.market_series[0].date == datetime.date(2026, 10, 31)
    assert history.store_series[0].points[1].price == 8.99
    assert history.has_more is True
    assert api.last_params == {
        "days": "30",
        "granularity": "weekly",
        "state": "SP",
        "store_limit": "10",
    }

    market = history.to_dataframe()
    assert market["median_price"].tolist() == [9.49, 9.59]
    assert market["ean"].tolist() == ["7894900011517", "7894900011517"]

    stores = history.to_dataframe(series="stores")
    assert stores["store_name"].tolist() == ["Supermercado Modelo", "Supermercado Modelo"]
    assert stores["price"].tolist() == [8.99, 8.99]
    assert "points" not in stores.columns


def test_coverage_posts_the_codes(api: FakeAPI) -> None:
    api.respond("POST", "/api/v1/market/products/coverage", "checkCatalogCoverage.json")

    with api.client() as client:
        coverage = client.products.coverage([" 7894900011517", "7891991000826", "0000000000000"])

    assert coverage.summary.coverage_pct == 66.67
    assert [item.found for item in coverage.data] == [True, True, False]
    assert api.last_request.method == "POST"
    assert api.last_request.headers["Content-Type"] == "application/json"
    assert api.last_request.read() == (
        b'{"eans":["7894900011517","7891991000826","0000000000000"]}'
    )


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
        client.products.coverage(["7894900011517"] * 501)


async def test_async_products_share_the_same_operations(api: FakeAPI) -> None:
    api.respond("GET", PRODUCT, "getProductByEan.json")
    api.respond("GET", CATALOG, "getCatalog.json")

    async with api.async_client() as client:
        product = await client.products.get("7894900011517")
        page = await client.products.catalog(search="coca")
        eans = [item.ean async for item in page.iter_all()]

    assert product.product_name == "Refrigerante Coca-Cola 2L"
    assert isinstance(page, models.AsyncCatalogPage)
    assert eans == ["7894900011517", "7894900027013"]
    assert client.usage.spent == 2


def api_fixture(name: str) -> dict[str, Any]:
    from conftest import load_fixture

    payload: dict[str, Any] = load_fixture(name)
    return payload
