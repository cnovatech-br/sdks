from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from cnovatech.datamarket import errors, models

if TYPE_CHECKING:
    from conftest import FakeAPI


def test_stores_by_brand(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/market/brands/COCA-COLA/stores", "getStoresByBrand.json")

    with api.client() as client:
        result = client.brands.stores("COCA-COLA", state="sp", min_product_count=5)

    assert isinstance(result, models.StoresByBrandResponse)
    assert result.brand == "COCA-COLA"
    assert result.summary.store_count == 2
    assert result.data[0].availability_pct == 92.1
    assert result.data[0].last_collected_date == datetime.date(2026, 11, 2)
    assert api.last_params == {"state": "SP", "min_product_count": "5"}
    assert result.to_dataframe()["brand"].tolist() == ["COCA-COLA", "COCA-COLA"]


def test_brand_is_percent_encoded_in_the_path(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/market/brands/Coca-Cola / Zero/stores", "getStoresByBrand.json")

    with api.client() as client:
        client.brands.stores("Coca-Cola / Zero")

    sent_path = api.last_request.url.raw_path.split(b"?", 1)[0]
    assert sent_path == b"/api/v1/market/brands/Coca-Cola%20%2F%20Zero/stores"


def test_blank_brand_is_rejected_before_sending(api: FakeAPI) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="brand"):
        client.brands.stores("  ")

    assert api.requests == []


async def test_async_stores_by_brand(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/market/brands/GALLO/stores", "getStoresByBrand.json")

    async with api.async_client() as client:
        result = await client.brands.stores("GALLO", channel="e-commerce")

    assert result.summary.offer_count == 60
    assert api.last_params == {"channel": "e-commerce", "min_product_count": "1"}
