"""Models of the brands resource."""

from __future__ import annotations

import datetime

from pydantic import Field

from .common import Record, TabularResponse, Usage

__all__ = ["StoreByBrand", "StoresByBrandResponse", "StoresByBrandSummary"]


class StoreByBrand(Record):
    """A store that sells the brand, with the brand's metrics in that store."""

    store_id: str
    store_name: str
    city: str | None = None
    state: str
    channel: str
    product_count: int
    category_count: int = 0
    department_count: int = 0
    avg_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    price_cv_pct: float | None = None
    availability_pct: float | None = None
    available_count: int = 0
    unavailable_count: int = 0
    last_collected_date: datetime.date | None = None


class StoresByBrandSummary(Record):
    """The brand in the market, summed over every store of the result."""

    store_count: int = 0
    state_count: int = 0
    offer_count: int = 0
    avg_price: float | None = None
    avg_availability_pct: float | None = None


class StoresByBrandResponse(TabularResponse):
    """Stores that sell a brand, from the one with most products to the one with fewest."""

    brand: str
    summary: StoresByBrandSummary
    data: list[StoreByBrand] = Field(default_factory=list)
    usage: Usage
