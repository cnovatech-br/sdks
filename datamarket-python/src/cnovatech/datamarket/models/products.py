"""Models of the products resource: catalogue, departments, brands, product lookup and coverage."""

from __future__ import annotations

import datetime
from typing import ClassVar

from pydantic import Field

from cnovatech.sdk_core.pagination import AsyncPage, SyncPage

from .common import Record, TabularResponse, Usage

__all__ = [
    "AsyncBrandsPage",
    "AsyncCatalogPage",
    "AsyncProductsByBrandPage",
    "Brand",
    "BrandProduct",
    "BrandsPage",
    "CatalogPage",
    "CatalogProduct",
    "Category",
    "CoverageItem",
    "CoverageResponse",
    "CoverageSummary",
    "Department",
    "DepartmentsResponse",
    "DepartmentsSummary",
    "MarketStats",
    "Product",
    "ProductsByBrandPage",
    "StoreOffer",
]


class CatalogProduct(Record):
    """A catalogue product with its market statistics across the monitored stores."""

    ean: str
    product_name: str
    brand: str | None = None
    category: str | None = None
    department: str | None = None
    image_url: str | None = None
    store_count: int
    state_count: int
    states: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    median_price: float | None = None
    price_range: float | None = None
    price_range_pct: float | None = None
    availability_pct: float | None = None


class CatalogPage(SyncPage[CatalogProduct]):
    """One page of the catalogue."""

    usage: Usage


class AsyncCatalogPage(AsyncPage[CatalogProduct]):
    """One page of the catalogue, from the asynchronous client."""

    usage: Usage


class Category(Record):
    """A category within a department."""

    category: str
    product_count: int


class Department(Record):
    """A department with its categories."""

    department: str
    product_count: int
    categories: list[Category] = Field(default_factory=list)


class DepartmentsSummary(Record):
    """Totals of the departments listing."""

    department_count: int
    category_count: int


class DepartmentsResponse(TabularResponse):
    """Departments and categories, with product counts: the valid values of the filters."""

    summary: DepartmentsSummary
    data: list[Department]
    usage: Usage


class Brand(Record):
    """A brand of the catalogue and the reach of its assortment."""

    brand: str
    product_count: int
    department_count: int | None = None
    category_count: int | None = None
    departments: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)


class BrandsPage(SyncPage[Brand]):
    """One page of brands."""

    usage: Usage


class AsyncBrandsPage(AsyncPage[Brand]):
    """One page of brands, from the asynchronous client."""

    usage: Usage


class BrandProduct(Record):
    """A product of a brand with its market statistics."""

    ean: str
    product_name: str
    brand: str | None = None
    category: str | None = None
    department: str | None = None
    image_url: str | None = None
    store_count: int
    availability_pct: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    median_price: float | None = None
    price_range: float | None = None
    price_cv_pct: float | None = None


class ProductsByBrandPage(SyncPage[BrandProduct]):
    """One page of the products of a brand."""

    usage: Usage


class AsyncProductsByBrandPage(AsyncPage[BrandProduct]):
    """One page of the products of a brand, from the asynchronous client."""

    usage: Usage


class MarketStats(Record):
    """Statistics of a product across the monitored stores, before any filter."""

    store_count: int
    state_count: int
    states: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    min_price: float | None = None
    max_price: float | None = None
    avg_price: float | None = None
    median_price: float | None = None
    price_range: float | None = None
    price_range_pct: float | None = None
    availability_pct: float | None = None


class StoreOffer(Record):
    """The product in one store: price, conditions and availability at the last collection."""

    store_id: str
    store_name: str
    city: str | None = None
    state: str
    channel: str
    price: float
    list_price: float | None = None
    discount_pct: float | None = None
    wholesale_price: float | None = None
    wholesale_min_qty: int | None = None
    installment_count: int | None = None
    installment_value: float | None = None
    available: bool
    stock_qty: int | None = None
    seller_name: str | None = None
    seller_type: str | None = None
    product_url: str | None = None
    image_url: str | None = None
    collected_at: datetime.datetime | None = None


class Product(TabularResponse):
    """A product, its market and the offer of each store. ``to_dataframe()`` gives one row per offer."""

    rows_field: ClassVar[str] = "offers"

    ean: str
    product_name: str
    brand: str
    category: str
    department: str
    image_url: str | None = None
    market: MarketStats
    offers: list[StoreOffer] = Field(default_factory=list)
    usage: Usage


class CoverageItem(Record):
    """One code of the submitted list and what the catalogue has for it."""

    ean: str
    queried_as: str
    found: bool
    product_name: str | None = None
    brand: str | None = None
    category: str | None = None
    department: str | None = None
    store_count: int | None = None
    state_count: int | None = None
    min_price: float | None = None
    max_price: float | None = None
    median_price: float | None = None


class CoverageSummary(Record):
    """How much of the submitted list the catalogue covers."""

    checked_count: int
    covered_count: int
    missing_count: int
    invalid_count: int
    coverage_pct: float


class CoverageResponse(TabularResponse):
    """Result of a coverage check: one item per valid code submitted."""

    summary: CoverageSummary
    data: list[CoverageItem]
    usage: Usage
