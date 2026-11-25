"""Models of the trend endpoints: rankings, per-product detail and per-store lists.

Three levels answer three questions. The rankings say which products changed
price, went on promotion or went out of stock in the window. The per-product
detail says what happened to one of them, store by store, as events with a
date. The per-store lists say what one store is promoting and what is missing
from its shelf.

The API returns events and dates, never the log of collections: how often
each store is collected is not exposed. Dates are therefore ``datetime.date``
objects, and the only timestamp is ``last_collected_at`` in a ranking summary.
"""

from __future__ import annotations

import datetime

from pydantic import Field

from cnovatech.sdk_core.pagination import AsyncPage, SyncPage

from .common import APIResponse, Record, StoreRef, Usage

__all__ = [
    "AsyncPriceChangesPage",
    "AsyncProductPriceChangesPage",
    "AsyncProductPromotionsPage",
    "AsyncProductStockoutsPage",
    "AsyncPromotionsPage",
    "AsyncStockoutsPage",
    "AsyncStorePromotionsPage",
    "AsyncStoreStockoutsPage",
    "CategoryPromotions",
    "CategoryStockouts",
    "DayPromotions",
    "DayStockouts",
    "PriceChange",
    "PriceChangeProduct",
    "PriceChangesPage",
    "PriceChangesSummary",
    "ProductPriceChangesPage",
    "ProductPriceChangesSummary",
    "ProductPromotionsPage",
    "ProductPromotionsSummary",
    "ProductStockoutsPage",
    "ProductStockoutsSummary",
    "PromotionMarket",
    "PromotionPeriod",
    "PromotionProduct",
    "PromotionsPage",
    "PromotionsSummary",
    "StatePromotions",
    "StateRepricing",
    "StateStockouts",
    "StockoutMarket",
    "StockoutPeriod",
    "StockoutProduct",
    "StockoutsPage",
    "StockoutsSummary",
    "StorePriceChanges",
    "StorePromotion",
    "StorePromotionProduct",
    "StorePromotionsPage",
    "StorePromotionsSummary",
    "StoreStockout",
    "StoreStockoutProduct",
    "StoreStockoutsPage",
    "StoreStockoutsSummary",
    "TrendProduct",
    "TrendStore",
]


class TrendProduct(Record):
    """The identity of a product in a trend row."""

    ean: str
    product_name: str
    brand: str | None = None
    category: str | None = None
    department: str | None = None
    image_url: str | None = None


class TrendStore(Record):
    """The identity of a store in a per-product detail, with the product's page in it."""

    store_id: str
    store_name: str
    city: str | None = None
    state: str | None = None
    product_url: str | None = None


# --- rankings -----------------------------------------------------------------


class PriceChangeProduct(TrendProduct):
    """A product in the price change ranking.

    ``price_change_count`` is a floor: stores are collected in rotation, so
    only a change seen between two collections is counted.
    """

    store_count: int
    repriced_store_count: int
    repriced_store_pct: float
    price_change_count: int
    price_increase_store_count: int = 0
    price_decrease_store_count: int = 0
    price_variation_pct: float | None = None


class PriceChangesSummary(Record):
    """Totals of the price change ranking, over every product of the result."""

    product_count: int
    price_change_count: int = 0
    median_repriced_store_pct: float | None = None
    median_price_variation_pct: float | None = None
    last_collected_at: datetime.datetime | None = None


class PriceChangesEnvelope(APIResponse):
    """What surrounds the rows of the price change ranking."""

    period_days: int
    summary: PriceChangesSummary


class PriceChangesPage(SyncPage[PriceChangeProduct], PriceChangesEnvelope):
    """One page of the price change ranking."""

    usage: Usage


class AsyncPriceChangesPage(AsyncPage[PriceChangeProduct], PriceChangesEnvelope):
    """One page of the price change ranking, from the asynchronous client."""

    usage: Usage


class PromotionProduct(TrendProduct):
    """A product in the promotion ranking."""

    store_count: int
    promo_store_count: int
    promo_store_pct: float
    median_discount_pct: float | None = None
    max_discount_pct: float | None = None


class PromotionsSummary(Record):
    """Totals of the promotion ranking, over every product of the result."""

    product_count: int
    median_promo_store_pct: float | None = None
    median_discount_pct: float | None = None
    last_collected_at: datetime.datetime | None = None


class PromotionsEnvelope(APIResponse):
    """What surrounds the rows of the promotion ranking."""

    period_days: int
    summary: PromotionsSummary


class PromotionsPage(SyncPage[PromotionProduct], PromotionsEnvelope):
    """One page of the promotion ranking."""

    usage: Usage


class AsyncPromotionsPage(AsyncPage[PromotionProduct], PromotionsEnvelope):
    """One page of the promotion ranking, from the asynchronous client."""

    usage: Usage


class StockoutProduct(TrendProduct):
    """A product in the stockout ranking.

    A stockout is a store that sold the product in the window and has it
    unavailable now; ``store_count`` counts the stores that sold it.
    """

    store_count: int
    stockout_store_count: int
    stockout_store_pct: float


class StockoutsSummary(Record):
    """Totals of the stockout ranking, over every product of the result."""

    product_count: int
    median_stockout_store_pct: float | None = None
    last_collected_at: datetime.datetime | None = None


class StockoutsEnvelope(APIResponse):
    """What surrounds the rows of the stockout ranking."""

    period_days: int
    summary: StockoutsSummary


class StockoutsPage(SyncPage[StockoutProduct], StockoutsEnvelope):
    """One page of the stockout ranking."""

    usage: Usage


class AsyncStockoutsPage(AsyncPage[StockoutProduct], StockoutsEnvelope):
    """One page of the stockout ranking, from the asynchronous client."""

    usage: Usage


# --- one product, store by store ----------------------------------------------


class ProductEnvelope(APIResponse):
    """The product a detail is about, and its window."""

    ean: str
    product_name: str
    brand: str | None = None
    category: str | None = None
    department: str | None = None
    image_url: str | None = None
    period_days: int


class PriceChange(Record):
    """One price change seen in a store: the day, the previous price and the new one."""

    change_date: datetime.date
    previous_price: float
    price: float
    change_pct: float


class StorePriceChanges(TrendStore):
    """The price of the product in one store over the window, and each change."""

    price: float
    price_change_count: int
    min_price: float
    max_price: float
    price_variation_pct: float | None = None
    price_diff_pct: float | None = None
    last_collected_date: datetime.date
    changes: list[PriceChange] = Field(default_factory=list)


class ProductPriceChangesSummary(Record):
    """Totals of the price changes of a product, over every store."""

    store_count: int
    repriced_store_count: int
    repriced_store_pct: float | None = None
    price_change_count: int
    price_increase_store_count: int
    price_decrease_store_count: int
    median_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    price_variation_pct: float | None = None
    last_collected_date: datetime.date | None = None


class StateRepricing(Record):
    """The stores of one state that changed the price, over the ones selling the product."""

    state: str
    store_count: int
    repriced_store_count: int
    repriced_store_pct: float | None = None


class ProductPriceChangesEnvelope(ProductEnvelope):
    """Totals and the breakdown by state; they describe every store, not only the page."""

    summary: ProductPriceChangesSummary
    by_state: list[StateRepricing] = Field(default_factory=list)


class ProductPriceChangesPage(SyncPage[StorePriceChanges], ProductPriceChangesEnvelope):
    """The price changes of one product: one page of its stores."""

    usage: Usage


class AsyncProductPriceChangesPage(AsyncPage[StorePriceChanges], ProductPriceChangesEnvelope):
    """The price changes of one product, from the asynchronous client."""

    usage: Usage


class PromotionPeriod(Record):
    """A stretch on promotion: the first and the last day it was seen, and its latest prices."""

    start_date: datetime.date
    end_date: datetime.date
    list_price: float
    price: float
    discount_pct: float


class StorePromotion(TrendStore):
    """The promotion of the product in one store over the window."""

    on_promotion: bool
    list_price: float
    price: float
    discount_pct: float
    promo_day_count: int
    min_discount_pct: float
    max_discount_pct: float
    median_discount_pct: float
    last_promo_date: datetime.date
    periods: list[PromotionPeriod] = Field(default_factory=list)


class ProductPromotionsSummary(Record):
    """Totals of the promotions of a product, over every store."""

    store_count: int
    promo_store_count: int
    promo_store_pct: float | None = None
    on_promotion_store_count: int
    median_list_price: float | None = None
    median_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    median_discount_pct: float | None = None
    max_discount_pct: float | None = None
    promo_day_count: int
    last_promo_date: datetime.date | None = None


class DayPromotions(Record):
    """One day of the window: the stores on promotion, from each store's last known state."""

    date: datetime.date
    store_count: int
    promo_store_count: int
    promo_store_pct: float | None = None
    median_discount_pct: float | None = None


class StatePromotions(Record):
    """The stores of one state that promoted the product, over the ones selling it."""

    state: str
    store_count: int
    promo_store_count: int
    promo_store_pct: float | None = None


class ProductPromotionsEnvelope(ProductEnvelope):
    """Totals, the series by day and the breakdown by state; they describe every store."""

    summary: ProductPromotionsSummary
    by_day: list[DayPromotions] = Field(default_factory=list)
    by_state: list[StatePromotions] = Field(default_factory=list)


class ProductPromotionsPage(SyncPage[StorePromotion], ProductPromotionsEnvelope):
    """The promotions of one product: one page of the stores that promoted it."""

    usage: Usage


class AsyncProductPromotionsPage(AsyncPage[StorePromotion], ProductPromotionsEnvelope):
    """The promotions of one product, from the asynchronous client."""

    usage: Usage


class StockoutPeriod(Record):
    """A gap in stock: the day it was seen, the day the product was seen back, and its length.

    ``end_date`` is ``None`` while the product is still missing.
    """

    start_date: datetime.date
    end_date: datetime.date | None = None
    day_count: int


class StoreStockout(TrendStore):
    """The availability of the product in one store over the window."""

    available: bool
    unavailable_since_date: datetime.date | None = None
    unavailable_day_count: int
    last_available_date: datetime.date
    last_collected_date: datetime.date
    periods: list[StockoutPeriod] = Field(default_factory=list)


class ProductStockoutsSummary(Record):
    """Totals of the stockouts of a product, over every store.

    ``never_available_store_count`` is the stores that list the product but
    never had it available in the window: a listing they stopped selling,
    left out of ``store_count`` instead of counted as a stockout.
    """

    store_count: int
    stockout_store_count: int
    stockout_store_pct: float | None = None
    stockout_in_period_store_count: int
    stockout_day_count: int
    stockout_state_count: int
    median_unavailable_day_count: float | None = None
    never_available_store_count: int
    last_collected_date: datetime.date | None = None


class DayStockouts(Record):
    """One day of the window: the stores without the product, from each store's last known state."""

    date: datetime.date
    store_count: int
    unavailable_store_count: int
    unavailable_store_pct: float | None = None


class StateStockouts(Record):
    """The stores of one state that are out of stock, over the ones selling the product."""

    state: str
    store_count: int
    stockout_store_count: int
    stockout_store_pct: float | None = None


class ProductStockoutsEnvelope(ProductEnvelope):
    """Totals, the series by day and the breakdown by state; they describe every store."""

    summary: ProductStockoutsSummary
    by_day: list[DayStockouts] = Field(default_factory=list)
    by_state: list[StateStockouts] = Field(default_factory=list)


class ProductStockoutsPage(SyncPage[StoreStockout], ProductStockoutsEnvelope):
    """The stockouts of one product: one page of its stores."""

    usage: Usage


class AsyncProductStockoutsPage(AsyncPage[StoreStockout], ProductStockoutsEnvelope):
    """The stockouts of one product, from the asynchronous client."""

    usage: Usage


# --- one store, product by product --------------------------------------------


class StockoutMarket(Record):
    """The same product in the other stores: missing here only, or across the market."""

    store_count: int
    stockout_store_count: int
    stockout_store_pct: float | None = None


class StoreStockoutProduct(TrendProduct):
    """A product that went missing in the store at some point of the window."""

    available: bool
    unavailable_since_date: datetime.date | None = None
    unavailable_day_count: int | None = None
    last_available_date: datetime.date | None = None
    last_collected_date: datetime.date | None = None
    periods: list[StockoutPeriod] = Field(default_factory=list)
    market: StockoutMarket


class StoreStockoutsSummary(Record):
    """Totals of the stockouts of a store, over the products of the catalogue filters."""

    sold_product_count: int
    stockout_count: int
    stockout_pct: float | None = None
    recovered_count: int


class CategoryStockouts(Record):
    """The stockouts of the store in one category."""

    category: str
    product_count: int
    stockout_count: int
    stockout_pct: float | None = None


class StoreStockoutsEnvelope(APIResponse):
    """The store, the window, the totals and the categories with the most stockouts."""

    store: StoreRef
    period_days: int
    summary: StoreStockoutsSummary
    by_category: list[CategoryStockouts] = Field(default_factory=list)


class StoreStockoutsPage(SyncPage[StoreStockoutProduct], StoreStockoutsEnvelope):
    """One page of the products that went missing in a store."""

    usage: Usage


class AsyncStoreStockoutsPage(AsyncPage[StoreStockoutProduct], StoreStockoutsEnvelope):
    """One page of the products that went missing in a store, from the asynchronous client."""

    usage: Usage


class PromotionMarket(Record):
    """The same product in the other stores: how many sell it and how many promoted it."""

    store_count: int
    promo_store_count: int
    promo_store_pct: float | None = None


class StorePromotionProduct(TrendProduct):
    """A product the store advertised on promotion in the window.

    ``always_on_promotion`` marks a product that was on promotion every time
    it was seen available: a list price nobody was charged in the window.
    """

    available: bool
    on_promotion: bool
    always_on_promotion: bool
    list_price: float
    price: float
    discount_pct: float
    min_discount_pct: float | None = None
    max_discount_pct: float | None = None
    median_discount_pct: float | None = None
    promo_day_count: int | None = None
    last_promo_date: datetime.date | None = None
    periods: list[PromotionPeriod] = Field(default_factory=list)
    market: PromotionMarket


class StorePromotionsSummary(Record):
    """Totals of the promotions of a store, over the products of the catalogue filters."""

    sold_product_count: int
    promo_product_count: int
    on_promotion_count: int
    on_promotion_pct: float | None = None
    ended_promotion_count: int
    always_on_promotion_count: int
    median_discount_pct: float | None = None


class CategoryPromotions(Record):
    """The promotions of the store in one category."""

    category: str
    product_count: int
    on_promotion_count: int
    on_promotion_pct: float | None = None


class StorePromotionsEnvelope(APIResponse):
    """The store, the window, the totals and the categories with the most promotions."""

    store: StoreRef
    period_days: int
    summary: StorePromotionsSummary
    by_category: list[CategoryPromotions] = Field(default_factory=list)


class StorePromotionsPage(SyncPage[StorePromotionProduct], StorePromotionsEnvelope):
    """One page of the products a store advertised on promotion."""

    usage: Usage


class AsyncStorePromotionsPage(AsyncPage[StorePromotionProduct], StorePromotionsEnvelope):
    """One page of the products a store advertised on promotion, from the asynchronous client."""

    usage: Usage
