"""Operation definitions, one function per API endpoint.

Everything an endpoint needs, from its path and parameters to its quota
estimate, is declared here and nowhere else. Resources call these functions;
transports execute the result. Paginated endpoints take the page model as
their first argument so the synchronous and asynchronous resources share
one definition.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, TypeVar

from pydantic import BaseModel

from cnovatech.datamarket.errors import StoreNotFoundError
from cnovatech.datamarket.models.account import ApiKeys, Profile, UsageHistory
from cnovatech.datamarket.models.brands import StoresByBrandResponse
from cnovatech.datamarket.models.common import Health
from cnovatech.datamarket.models.history import PriceHistory
from cnovatech.datamarket.models.products import (
    CoverageResponse,
    DepartmentsResponse,
    Product,
)
from cnovatech.datamarket.models.stores import CompetitivenessResponse, CompetitorsResponse
from cnovatech.sdk_core import pricing
from cnovatech.sdk_core.models import parser_for
from cnovatech.sdk_core.operation import Operation
from cnovatech.sdk_core.validation import (
    validate_batch,
    validate_identifier,
    validate_limit,
    validate_page,
    validate_path_segment,
    validate_product_code,
    validate_state,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from cnovatech.datamarket.types import (
        Channel,
        ComparisonSortBy,
        Granularity,
        LogStatus,
        MarketScope,
        OfferSortBy,
        OpportunityType,
        PricePosition,
        SortOrder,
    )

PageT = TypeVar("PageT", bound=BaseModel)

CATALOG_PATH = "/market/products/catalog"
DEPARTMENTS_PATH = "/market/products/departments"
BRANDS_PATH = "/market/products/brands"
PRODUCTS_BY_BRAND_PATH = "/market/products/by-brand"
PRODUCT_PATH = "/market/products/ean/{ean}"
PRICE_HISTORY_PATH = "/market/products/ean/{ean}/price-history"
COVERAGE_PATH = "/market/products/coverage"
STORES_PATH = "/market/stores"
ASSORTMENT_PATH = "/market/stores/{store_id}/assortment"
COMPETITIVENESS_PATH = "/market/stores/{store_id}/competitiveness"
COMPETITORS_PATH = "/market/stores/{store_id}/competitors"
COMPARISON_PATH = "/market/stores/{store_id}/competitors/{competitor_id}/products"
MARKET_POSITION_PATH = "/market/stores/{store_id}/market-position"
OPPORTUNITIES_PATH = "/market/stores/{store_id}/opportunities"
STORES_BY_BRAND_PATH = "/market/brands/{brand}/stores"
PROFILE_PATH = "/user/profile"
USAGE_PATH = "/user/usage"
LOGS_PATH = "/user/logs"
API_KEYS_PATH = "/user/api-keys"
HEALTH_PATH = "/health"

ENDPOINTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", CATALOG_PATH),
        ("GET", DEPARTMENTS_PATH),
        ("GET", BRANDS_PATH),
        ("GET", PRODUCTS_BY_BRAND_PATH),
        ("GET", PRODUCT_PATH),
        ("GET", PRICE_HISTORY_PATH),
        ("POST", COVERAGE_PATH),
        ("GET", STORES_PATH),
        ("GET", ASSORTMENT_PATH),
        ("GET", COMPETITIVENESS_PATH),
        ("GET", COMPETITORS_PATH),
        ("GET", COMPARISON_PATH),
        ("GET", MARKET_POSITION_PATH),
        ("GET", OPPORTUNITIES_PATH),
        ("GET", STORES_BY_BRAND_PATH),
        ("GET", PROFILE_PATH),
        ("GET", USAGE_PATH),
        ("GET", LOGS_PATH),
        ("GET", API_KEYS_PATH),
        ("GET", HEALTH_PATH),
    }
)
"""Every (method, path) this module implements, for the contract test against the OpenAPI document."""

MAX_LIMIT_CATALOG = 100
MAX_LIMIT_BRANDS = 100
MAX_LIMIT_PRODUCTS_BY_BRAND = 100
MAX_LIMIT_STORES = 100
MAX_LIMIT_ASSORTMENT = 1000
MAX_LIMIT_COMPETITORS = 50
MAX_LIMIT_COMPETITIVENESS = 200
MAX_LIMIT_COMPARISON = 100
MAX_LIMIT_MARKET_POSITION = 10_000
MAX_LIMIT_OPPORTUNITIES = 1000
MAX_LIMIT_LOGS = 100
MAX_CODES_PER_COVERAGE = 500

_STORE_ROUTE_ERRORS: Mapping[int, type[StoreNotFoundError]] = {404: StoreNotFoundError}


# --- products -----------------------------------------------------------------


def catalog(
    page_model: type[PageT],
    *,
    search: str | None,
    brand: str | None,
    category: str | None,
    department: str | None,
    state: str | None,
    channel: Channel | None,
    min_price: float | None,
    max_price: float | None,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /market/products/catalog``: one unit per page."""
    return Operation(
        method="GET",
        path=CATALOG_PATH,
        parse=parser_for(page_model),
        params={
            "search": search,
            "brand": brand,
            "category": category,
            "department": department,
            "state": validate_state(state),
            "channel": channel,
            "min_price": min_price,
            "max_price": max_price,
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_CATALOG),
        },
        estimated_cost=pricing.query_cost(),
    )


def departments() -> Operation[DepartmentsResponse]:
    """``GET /market/products/departments``: one unit."""
    return Operation(
        method="GET",
        path=DEPARTMENTS_PATH,
        parse=parser_for(DepartmentsResponse),
        estimated_cost=pricing.query_cost(),
    )


def brands(
    page_model: type[PageT],
    *,
    search: str | None,
    department: str | None,
    category: str | None,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /market/products/brands``: one unit per page."""
    return Operation(
        method="GET",
        path=BRANDS_PATH,
        parse=parser_for(page_model),
        params={
            "search": search,
            "department": department,
            "category": category,
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_BRANDS),
        },
        estimated_cost=pricing.query_cost(),
    )


def products_by_brand(
    page_model: type[PageT],
    *,
    brand: str,
    category: str | None,
    department: str | None,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /market/products/by-brand``: one unit per page."""
    return Operation(
        method="GET",
        path=PRODUCTS_BY_BRAND_PATH,
        parse=parser_for(page_model),
        params={
            "brand": brand,
            "category": category,
            "department": department,
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_PRODUCTS_BY_BRAND),
        },
        estimated_cost=pricing.query_cost(),
    )


def product(
    ean: str,
    *,
    state: str | None,
    city: str | None,
    channel: Channel | None,
    sort_by: OfferSortBy,
    sort_order: SortOrder,
) -> Operation[Product]:
    """``GET /market/products/ean/{ean}``: one unit."""
    return Operation(
        method="GET",
        path=PRODUCT_PATH.format(ean=validate_product_code(ean, name="ean")),
        parse=parser_for(Product),
        params={
            "state": validate_state(state),
            "city": city,
            "channel": channel,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
        estimated_cost=pricing.query_cost(),
    )


def price_history(
    ean: str,
    *,
    days: int,
    granularity: Granularity,
    state: str | None,
    store_limit: int,
) -> Operation[PriceHistory]:
    """``GET /market/products/ean/{ean}/price-history``: one unit."""
    return Operation(
        method="GET",
        path=PRICE_HISTORY_PATH.format(ean=validate_product_code(ean, name="ean")),
        parse=parser_for(PriceHistory),
        params={
            "days": days,
            "granularity": granularity,
            "state": validate_state(state),
            "store_limit": store_limit,
        },
        estimated_cost=pricing.query_cost(),
    )


def coverage(eans: Sequence[str]) -> Operation[CoverageResponse]:
    """``POST /market/products/coverage``: one unit per started block of 250 codes."""
    codes = validate_batch(eans, name="eans", maximum=MAX_CODES_PER_COVERAGE)
    return Operation(
        method="POST",
        path=COVERAGE_PATH,
        parse=parser_for(CoverageResponse),
        json_body={"eans": codes},
        estimated_cost=pricing.batch_cost(len(codes)),
    )


# --- stores -------------------------------------------------------------------


def stores(
    page_model: type[PageT],
    *,
    search: str | None,
    state: str | None,
    city: str | None,
    channel: Channel | None,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /market/stores``: one unit per page."""
    return Operation(
        method="GET",
        path=STORES_PATH,
        parse=parser_for(page_model),
        params={
            "search": search,
            "state": validate_state(state),
            "city": city,
            "channel": channel,
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_STORES),
        },
        estimated_cost=pricing.query_cost(),
    )


def assortment(
    page_model: type[PageT], *, store_id: str, limit: int, page: int
) -> Operation[PageT]:
    """``GET /market/stores/{store_id}/assortment``: two units per started block of 250 rows."""
    rows = validate_limit(limit, maximum=MAX_LIMIT_ASSORTMENT)
    return Operation(
        method="GET",
        path=ASSORTMENT_PATH.format(store_id=validate_identifier(store_id, name="store_id")),
        parse=parser_for(page_model),
        params={"page": validate_page(page), "limit": rows},
        estimated_cost=pricing.export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
    )


def competitors(
    store_id: str, *, min_overlap_pct: float, limit: int
) -> Operation[CompetitorsResponse]:
    """``GET /market/stores/{store_id}/competitors``: one unit per competitor returned."""
    items = validate_limit(limit, maximum=MAX_LIMIT_COMPETITORS)
    return Operation(
        method="GET",
        path=COMPETITORS_PATH.format(store_id=validate_identifier(store_id, name="store_id")),
        parse=parser_for(CompetitorsResponse),
        params={"min_overlap_pct": min_overlap_pct, "limit": items},
        estimated_cost=pricing.per_item_cost(items),
        status_overrides=_STORE_ROUTE_ERRORS,
    )


def competitiveness(
    store_id: str,
    *,
    min_overlap_pct: float,
    limit: int,
    market_scope: MarketScope,
    state: str | None,
) -> Operation[CompetitivenessResponse]:
    """``GET /market/stores/{store_id}/competitiveness``: one unit per competitor returned."""
    items = validate_limit(limit, maximum=MAX_LIMIT_COMPETITIVENESS)
    return Operation(
        method="GET",
        path=COMPETITIVENESS_PATH.format(store_id=validate_identifier(store_id, name="store_id")),
        parse=parser_for(CompetitivenessResponse),
        params={
            "min_overlap_pct": min_overlap_pct,
            "limit": items,
            "market_scope": market_scope,
            "state": validate_state(state),
        },
        estimated_cost=pricing.per_item_cost(items),
        status_overrides=_STORE_ROUTE_ERRORS,
    )


def comparison(
    page_model: type[PageT],
    *,
    store_id: str,
    competitor_id: str,
    price_position: PricePosition,
    search: str | None,
    sort_by: ComparisonSortBy,
    sort_order: SortOrder,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /market/stores/{store_id}/competitors/{competitor_id}/products``: two units per started block of 250 rows."""
    rows = validate_limit(limit, maximum=MAX_LIMIT_COMPARISON)
    return Operation(
        method="GET",
        path=COMPARISON_PATH.format(
            store_id=validate_identifier(store_id, name="store_id"),
            competitor_id=validate_identifier(competitor_id, name="competitor_id"),
        ),
        parse=parser_for(page_model),
        params={
            "price_position": price_position,
            "search": search,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": validate_page(page),
            "limit": rows,
        },
        estimated_cost=pricing.export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
    )


def market_position(
    page_model: type[PageT],
    *,
    store_id: str,
    market_scope: MarketScope,
    state: str | None,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /market/stores/{store_id}/market-position``: two units per started block of 250 rows."""
    rows = validate_limit(limit, maximum=MAX_LIMIT_MARKET_POSITION)
    return Operation(
        method="GET",
        path=MARKET_POSITION_PATH.format(store_id=validate_identifier(store_id, name="store_id")),
        parse=parser_for(page_model),
        params={
            "market_scope": market_scope,
            "state": validate_state(state),
            "page": validate_page(page),
            "limit": rows,
        },
        estimated_cost=pricing.export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
    )


def opportunities(
    page_model: type[PageT],
    *,
    store_id: str,
    opportunity_type: OpportunityType | None,
    min_diff_pct: float,
    max_diff_pct: float,
    min_store_count: int,
    state: str | None,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /market/stores/{store_id}/opportunities``: two units per started block of 250 rows."""
    rows = validate_limit(limit, maximum=MAX_LIMIT_OPPORTUNITIES)
    return Operation(
        method="GET",
        path=OPPORTUNITIES_PATH.format(store_id=validate_identifier(store_id, name="store_id")),
        parse=parser_for(page_model),
        params={
            "opportunity_type": opportunity_type,
            "min_diff_pct": min_diff_pct,
            "max_diff_pct": max_diff_pct,
            "min_store_count": min_store_count,
            "state": validate_state(state),
            "page": validate_page(page),
            "limit": rows,
        },
        estimated_cost=pricing.export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
    )


# --- brands -------------------------------------------------------------------


def stores_by_brand(
    brand: str, *, state: str | None, channel: Channel | None, min_product_count: int
) -> Operation[StoresByBrandResponse]:
    """``GET /market/brands/{brand}/stores``: one unit."""
    return Operation(
        method="GET",
        path=STORES_BY_BRAND_PATH.format(brand=validate_path_segment(brand, name="brand")),
        parse=parser_for(StoresByBrandResponse),
        params={
            "state": validate_state(state),
            "channel": channel,
            "min_product_count": min_product_count,
        },
        estimated_cost=pricing.query_cost(),
    )


# --- account ------------------------------------------------------------------


def profile() -> Operation[Profile]:
    """``GET /user/profile``: free."""
    return Operation(method="GET", path=PROFILE_PATH, parse=parser_for(Profile))


def usage_history() -> Operation[UsageHistory]:
    """``GET /user/usage``: free."""
    return Operation(method="GET", path=USAGE_PATH, parse=parser_for(UsageHistory))


def logs(
    page_model: type[PageT],
    *,
    status: LogStatus | None,
    search: str | None,
    start_date: datetime.date | str | None,
    end_date: datetime.date | str | None,
    limit: int,
    page: int,
) -> Operation[PageT]:
    """``GET /user/logs``: free."""
    return Operation(
        method="GET",
        path=LOGS_PATH,
        parse=parser_for(page_model),
        params={
            "status_filter": status,
            "search": search,
            "start_date": _iso_date(start_date),
            "end_date": _iso_date(end_date),
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_LOGS),
        },
    )


def api_keys() -> Operation[ApiKeys]:
    """``GET /user/api-keys``: free."""
    return Operation(method="GET", path=API_KEYS_PATH, parse=parser_for(ApiKeys))


# --- status -------------------------------------------------------------------


def health() -> Operation[Health]:
    """``GET /health``: outside the API prefix, without authentication, free."""
    return Operation(
        method="GET",
        path=HEALTH_PATH,
        parse=parser_for(Health),
        requires_auth=False,
        under_api_prefix=False,
    )


def _iso_date(value: datetime.date | str | None) -> str | None:
    """``YYYY-MM-DD`` for a date; a datetime keeps its calendar day; strings pass through."""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value
