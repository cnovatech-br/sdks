"""Operation definitions, one function per API endpoint.

Everything an endpoint needs is declared here and nowhere else: where it
lives (an :class:`Endpoint`), its parameters, its validation and its quota
estimate. Resources call these functions; transports execute the result.
Paginated endpoints take the page model as their first argument so the
synchronous and asynchronous resources share one definition.
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
from cnovatech.datamarket.resources._pricing import (
    QUERY_COST,
    competitor_cost,
    coverage_cost,
    export_cost,
)
from cnovatech.datamarket.resources._validation import validate_ean, validate_state
from cnovatech.sdk_core.operation import Endpoint, Operation
from cnovatech.sdk_core.validation import (
    validate_batch,
    validate_identifier,
    validate_limit,
    validate_page,
    validate_path_segment,
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

CATALOG = Endpoint("GET", "/market/products/catalog")
DEPARTMENTS = Endpoint("GET", "/market/products/departments")
BRANDS = Endpoint("GET", "/market/products/brands")
PRODUCTS_BY_BRAND = Endpoint("GET", "/market/products/by-brand")
PRODUCT = Endpoint("GET", "/market/products/ean/{ean}")
PRICE_HISTORY = Endpoint("GET", "/market/products/ean/{ean}/price-history")
COVERAGE = Endpoint("POST", "/market/products/coverage")
STORES = Endpoint("GET", "/market/stores")
ASSORTMENT = Endpoint("GET", "/market/stores/{store_id}/assortment")
COMPETITIVENESS = Endpoint("GET", "/market/stores/{store_id}/competitiveness")
COMPETITORS = Endpoint("GET", "/market/stores/{store_id}/competitors")
COMPARISON = Endpoint("GET", "/market/stores/{store_id}/competitors/{competitor_id}/products")
MARKET_POSITION = Endpoint("GET", "/market/stores/{store_id}/market-position")
OPPORTUNITIES = Endpoint("GET", "/market/stores/{store_id}/opportunities")
STORES_BY_BRAND = Endpoint("GET", "/market/brands/{brand}/stores")
PROFILE = Endpoint("GET", "/user/profile")
USAGE = Endpoint("GET", "/user/usage")
LOGS = Endpoint("GET", "/user/logs")
API_KEYS = Endpoint("GET", "/user/api-keys")
HEALTH = Endpoint("GET", "/health", under_api_prefix=False, requires_auth=False)

ENDPOINTS: tuple[Endpoint, ...] = (
    CATALOG,
    DEPARTMENTS,
    BRANDS,
    PRODUCTS_BY_BRAND,
    PRODUCT,
    PRICE_HISTORY,
    COVERAGE,
    STORES,
    ASSORTMENT,
    COMPETITIVENESS,
    COMPETITORS,
    COMPARISON,
    MARKET_POSITION,
    OPPORTUNITIES,
    STORES_BY_BRAND,
    PROFILE,
    USAGE,
    LOGS,
    API_KEYS,
    HEALTH,
)
"""Every endpoint this module implements; the contract test compares it with the OpenAPI document."""

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
    return CATALOG.operation(
        page_model.model_validate,
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
        estimated_cost=QUERY_COST,
    )


def departments() -> Operation[DepartmentsResponse]:
    """``GET /market/products/departments``: one unit."""
    return DEPARTMENTS.operation(DepartmentsResponse.model_validate, estimated_cost=QUERY_COST)


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
    return BRANDS.operation(
        page_model.model_validate,
        params={
            "search": search,
            "department": department,
            "category": category,
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_BRANDS),
        },
        estimated_cost=QUERY_COST,
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
    return PRODUCTS_BY_BRAND.operation(
        page_model.model_validate,
        params={
            "brand": brand,
            "category": category,
            "department": department,
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_PRODUCTS_BY_BRAND),
        },
        estimated_cost=QUERY_COST,
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
    return PRODUCT.operation(
        Product.model_validate,
        params={
            "state": validate_state(state),
            "city": city,
            "channel": channel,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
        estimated_cost=QUERY_COST,
        ean=validate_ean(ean),
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
    return PRICE_HISTORY.operation(
        PriceHistory.model_validate,
        params={
            "days": days,
            "granularity": granularity,
            "state": validate_state(state),
            "store_limit": store_limit,
        },
        estimated_cost=QUERY_COST,
        ean=validate_ean(ean),
    )


def coverage(eans: Sequence[str]) -> Operation[CoverageResponse]:
    """``POST /market/products/coverage``: one unit per started block of 250 codes."""
    codes = validate_batch(eans, name="eans", maximum=MAX_CODES_PER_COVERAGE)
    return COVERAGE.operation(
        CoverageResponse.model_validate,
        json_body={"eans": codes},
        estimated_cost=coverage_cost(len(codes)),
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
    return STORES.operation(
        page_model.model_validate,
        params={
            "search": search,
            "state": validate_state(state),
            "city": city,
            "channel": channel,
            "page": validate_page(page),
            "limit": validate_limit(limit, maximum=MAX_LIMIT_STORES),
        },
        estimated_cost=QUERY_COST,
    )


def assortment(
    page_model: type[PageT], *, store_id: str, limit: int, page: int
) -> Operation[PageT]:
    """``GET /market/stores/{store_id}/assortment``: two units per started block of 250 rows."""
    rows = validate_limit(limit, maximum=MAX_LIMIT_ASSORTMENT)
    return ASSORTMENT.operation(
        page_model.model_validate,
        params={"page": validate_page(page), "limit": rows},
        estimated_cost=export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
        store_id=validate_identifier(store_id, name="store_id"),
    )


def competitors(
    store_id: str, *, min_overlap_pct: float, limit: int
) -> Operation[CompetitorsResponse]:
    """``GET /market/stores/{store_id}/competitors``: one unit per competitor returned."""
    items = validate_limit(limit, maximum=MAX_LIMIT_COMPETITORS)
    return COMPETITORS.operation(
        CompetitorsResponse.model_validate,
        params={"min_overlap_pct": min_overlap_pct, "limit": items},
        estimated_cost=competitor_cost(items),
        status_overrides=_STORE_ROUTE_ERRORS,
        store_id=validate_identifier(store_id, name="store_id"),
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
    return COMPETITIVENESS.operation(
        CompetitivenessResponse.model_validate,
        params={
            "min_overlap_pct": min_overlap_pct,
            "limit": items,
            "market_scope": market_scope,
            "state": validate_state(state),
        },
        estimated_cost=competitor_cost(items),
        status_overrides=_STORE_ROUTE_ERRORS,
        store_id=validate_identifier(store_id, name="store_id"),
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
    return COMPARISON.operation(
        page_model.model_validate,
        params={
            "price_position": price_position,
            "search": search,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page": validate_page(page),
            "limit": rows,
        },
        estimated_cost=export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
        store_id=validate_identifier(store_id, name="store_id"),
        competitor_id=validate_identifier(competitor_id, name="competitor_id"),
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
    return MARKET_POSITION.operation(
        page_model.model_validate,
        params={
            "market_scope": market_scope,
            "state": validate_state(state),
            "page": validate_page(page),
            "limit": rows,
        },
        estimated_cost=export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
        store_id=validate_identifier(store_id, name="store_id"),
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
    return OPPORTUNITIES.operation(
        page_model.model_validate,
        params={
            "opportunity_type": opportunity_type,
            "min_diff_pct": min_diff_pct,
            "max_diff_pct": max_diff_pct,
            "min_store_count": min_store_count,
            "state": validate_state(state),
            "page": validate_page(page),
            "limit": rows,
        },
        estimated_cost=export_cost(rows),
        status_overrides=_STORE_ROUTE_ERRORS,
        store_id=validate_identifier(store_id, name="store_id"),
    )


# --- brands -------------------------------------------------------------------


def stores_by_brand(
    brand: str, *, state: str | None, channel: Channel | None, min_product_count: int
) -> Operation[StoresByBrandResponse]:
    """``GET /market/brands/{brand}/stores``: one unit."""
    return STORES_BY_BRAND.operation(
        StoresByBrandResponse.model_validate,
        params={
            "state": validate_state(state),
            "channel": channel,
            "min_product_count": min_product_count,
        },
        estimated_cost=QUERY_COST,
        brand=validate_path_segment(brand, name="brand"),
    )


# --- account ------------------------------------------------------------------


def profile() -> Operation[Profile]:
    """``GET /user/profile``: free."""
    return PROFILE.operation(Profile.model_validate)


def usage_history() -> Operation[UsageHistory]:
    """``GET /user/usage``: free."""
    return USAGE.operation(UsageHistory.model_validate)


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
    return LOGS.operation(
        page_model.model_validate,
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
    return API_KEYS.operation(ApiKeys.model_validate)


# --- status -------------------------------------------------------------------


def health() -> Operation[Health]:
    """``GET /health``: outside the API prefix, without authentication, free."""
    return HEALTH.operation(Health.model_validate)


def _iso_date(value: datetime.date | str | None) -> str | None:
    """``YYYY-MM-DD`` for a date; a datetime keeps its calendar day; strings pass through."""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return value
