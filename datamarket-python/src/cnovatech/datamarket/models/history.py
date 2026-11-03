"""Models of the price history of a product."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, ClassVar, Literal

from pydantic import Field

from cnovatech.sdk_core.dataframe import build_dataframe

from .common import Record, TabularResponse, Usage

if TYPE_CHECKING:
    import pandas

__all__ = ["MarketBucket", "PriceHistory", "StorePoint", "StoreSeries"]


class MarketBucket(Record):
    """One period of the market series: the price consolidated across stores."""

    date: datetime.date
    median_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    store_count: int = 0


class StorePoint(Record):
    """One day of the price series of a store."""

    date: datetime.date
    price: float | None = None


class StoreSeries(Record):
    """The price series of the product in one store."""

    store_id: str | None = None
    store_name: str | None = None
    city: str | None = None
    state: str | None = None
    last_collected_at: datetime.datetime | None = None
    points: list[StorePoint] = Field(default_factory=list)


class PriceHistory(TabularResponse):
    """Price evolution of a product: the market series and the series of each store."""

    rows_field: ClassVar[str] = "market_series"

    ean: str
    granularity: str
    period_days: int
    currency: str = "BRL"
    market_series: list[MarketBucket] = Field(default_factory=list)
    store_count: int = 0
    has_more: bool = False
    store_series: list[StoreSeries] = Field(default_factory=list)
    usage: Usage

    def to_dataframe(
        self,
        *,
        include_envelope: bool = True,
        series: Literal["market", "stores"] = "market",
    ) -> pandas.DataFrame:
        """One row per period of the market series, or per store and day with ``series="stores"``.

        Requires pandas, available through the SDK's ``pandas`` extra.
        """
        rows_field = "market_series" if series == "market" else "store_series.points"
        return build_dataframe(self, rows_field=rows_field, include_envelope=include_envelope)
