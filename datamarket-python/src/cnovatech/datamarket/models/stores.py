"""Models of the stores resource: listing, assortment, competitors and price analyses."""

from __future__ import annotations

import datetime

from pydantic import Field

from cnovatech.sdk_core.pagination import AsyncPage, SyncPage

from .common import APIResponse, ListMeta, Record, StoreRef, TabularResponse, Usage

__all__ = [
    "AssortmentItem",
    "AssortmentPage",
    "AsyncAssortmentPage",
    "AsyncComparisonPage",
    "AsyncMarketPositionPage",
    "AsyncOpportunitiesPage",
    "AsyncStoresPage",
    "ComparisonItem",
    "ComparisonPage",
    "ComparisonSummary",
    "CompetitivenessItem",
    "CompetitivenessResponse",
    "CompetitivenessSummary",
    "Competitor",
    "CompetitorsResponse",
    "CompetitorsSummary",
    "MarketPositionItem",
    "MarketPositionPage",
    "MarketPositionStats",
    "MarketPositionSummary",
    "OpportunitiesPage",
    "OpportunitiesSummary",
    "Opportunity",
    "OpportunityMarketStats",
    "Store",
    "StoresPage",
]


class Store(StoreRef):
    """A monitored store."""

    omnichannel: bool = False
    product_count: int = 0
    last_collected_date: datetime.date | None = None


class StoresPage(SyncPage[Store]):
    """One page of monitored stores."""

    usage: Usage


class AsyncStoresPage(AsyncPage[Store]):
    """One page of monitored stores, from the asynchronous client."""

    usage: Usage


class StoreEnvelope(APIResponse):
    """Envelope of the analyses of one store."""

    store: StoreRef


class AssortmentItem(Record):
    """A product of a store's assortment, with its price and conditions at the last collection."""

    ean: str
    product_name: str | None = None
    brand: str | None = None
    department: str | None = None
    category: str | None = None
    image_url: str | None = None
    price: float | None = None
    list_price: float | None = None
    discount_pct: float | None = None
    wholesale_price: float | None = None
    wholesale_min_qty: int | None = None
    installment_count: int | None = None
    installment_value: float | None = None
    installment_total: float | None = None
    installment_has_interest: bool | None = None
    available: bool
    stock_qty: int | None = None
    sale_unit: str | None = None
    sale_qty: float | None = None
    collected_date: datetime.date | None = None


class AssortmentPage(SyncPage[AssortmentItem], StoreEnvelope):
    """One page of a store's assortment."""

    usage: Usage


class AsyncAssortmentPage(AsyncPage[AssortmentItem], StoreEnvelope):
    """One page of a store's assortment, from the asynchronous client."""

    usage: Usage


class Competitor(StoreRef):
    """A competing store, by assortment overlap with the queried store."""

    product_count: int = 0
    common_product_count: int = 0
    overlap_pct: float = 0
    avg_price: float | None = None
    median_price: float | None = None
    min_price: float | None = None
    max_price: float | None = None


class CompetitorsSummary(Record):
    """Base of the overlap: products with a price in the queried store."""

    product_count: int = 0


class CompetitorsResponse(TabularResponse):
    """Competitors of a store, from the largest to the smallest overlap."""

    store: StoreRef
    summary: CompetitorsSummary
    data: list[Competitor] = Field(default_factory=list)
    meta: ListMeta
    usage: Usage


class CompetitivenessItem(StoreRef):
    """Price position of the queried store against one competitor."""

    common_product_count: int = 0
    unavailable_count: int = 0
    below_count: int = 0
    aligned_count: int = 0
    above_count: int = 0
    below_pct: float | None = None
    aligned_pct: float | None = None
    above_pct: float | None = None
    median_price_diff_pct: float | None = None
    competitiveness_score: float | None = None


class CompetitivenessSummary(Record):
    """Totals of the competitiveness analysis."""

    product_count: int = 0
    competitiveness_score: float | None = None


class CompetitivenessResponse(TabularResponse):
    """Competitiveness of a store against each competitor, from the most to the least competitive."""

    store: StoreRef
    summary: CompetitivenessSummary
    data: list[CompetitivenessItem] = Field(default_factory=list)
    meta: ListMeta
    usage: Usage


class ComparisonItem(Record):
    """A product the queried store and the competitor both sell."""

    ean: str
    product_name: str | None = None
    brand: str | None = None
    department: str | None = None
    category: str | None = None
    image_url: str | None = None
    price: float
    available: bool
    competitor_price: float
    competitor_available: bool
    price_diff_pct: float | None = None
    price_position: str


class ComparisonSummary(Record):
    """Totals of the comparison, over every product in common."""

    common_product_count: int = 0
    below_count: int = 0
    aligned_count: int = 0
    above_count: int = 0
    unavailable_count: int = 0


class ComparisonEnvelope(APIResponse):
    """Envelope of a product-by-product comparison."""

    store: StoreRef
    competitor: StoreRef
    summary: ComparisonSummary


class ComparisonPage(SyncPage[ComparisonItem], ComparisonEnvelope):
    """One page of a product-by-product comparison with a competitor."""

    usage: Usage


class AsyncComparisonPage(AsyncPage[ComparisonItem], ComparisonEnvelope):
    """One page of a product-by-product comparison, from the asynchronous client."""

    usage: Usage


class MarketPositionStats(Record):
    """The market of a product, without the queried store."""

    store_count: int = 0
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    median_price: float | None = None
    mode_price: float | None = None
    availability_pct: float | None = None


class MarketPositionItem(Record):
    """A product of the store, its market and its position against the market median."""

    ean: str
    product_name: str | None = None
    brand: str | None = None
    department: str | None = None
    category: str | None = None
    image_url: str | None = None
    price: float
    list_price: float | None = None
    available: bool
    price_position: str | None = None
    price_diff_pct: float | None = None
    market: MarketPositionStats


class MarketPositionSummary(Record):
    """Totals of the market position, over every product and not only the page."""

    product_count: int = 0
    comparable_count: int = 0
    unavailable_count: int = 0


class MarketPositionEnvelope(APIResponse):
    """Envelope of the market position of a store."""

    store: StoreRef
    summary: MarketPositionSummary


class MarketPositionPage(SyncPage[MarketPositionItem], MarketPositionEnvelope):
    """One page of the market position of a store."""

    usage: Usage


class AsyncMarketPositionPage(AsyncPage[MarketPositionItem], MarketPositionEnvelope):
    """One page of the market position of a store, from the asynchronous client."""

    usage: Usage


class OpportunityMarketStats(Record):
    """The market of a product, without the queried store, over available offers only."""

    store_count: int = 0
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    median_price: float | None = None


class Opportunity(Record):
    """A repricing opportunity for one product."""

    ean: str
    product_name: str | None = None
    brand: str | None = None
    category: str | None = None
    department: str | None = None
    image_url: str | None = None
    price: float
    price_diff: float
    price_diff_pct: float
    price_rank: int
    opportunity_type: str
    market: OpportunityMarketStats


class OpportunitiesSummary(Record):
    """Totals of the opportunities analysis, over every product and not only the page."""

    product_count: int = 0
    increase_count: int = 0
    decrease_count: int = 0
    comfortable_count: int = 0
    avg_abs_price_diff_pct: float | None = None


class OpportunitiesEnvelope(APIResponse):
    """Envelope of the repricing opportunities of a store."""

    store: StoreRef
    summary: OpportunitiesSummary


class OpportunitiesPage(SyncPage[Opportunity], OpportunitiesEnvelope):
    """One page of repricing opportunities, from the largest to the smallest difference."""

    usage: Usage


class AsyncOpportunitiesPage(AsyncPage[Opportunity], OpportunitiesEnvelope):
    """One page of repricing opportunities, from the asynchronous client."""

    usage: Usage
