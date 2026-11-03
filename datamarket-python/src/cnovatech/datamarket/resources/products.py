"""Products: catalogue, departments, brands, lookup by EAN, price history and coverage."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from cnovatech.datamarket.models.products import (
    AsyncBrandsPage,
    AsyncCatalogPage,
    AsyncProductsByBrandPage,
    BrandsPage,
    CatalogPage,
    ProductsByBrandPage,
)
from cnovatech.datamarket.resources import _operations as operations
from cnovatech.datamarket.resources._base import AsyncResource, SyncResource
from cnovatech.sdk_core import pricing

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cnovatech.datamarket.models.history import PriceHistory
    from cnovatech.datamarket.models.products import (
        CoverageResponse,
        DepartmentsResponse,
        Product,
    )
    from cnovatech.datamarket.types import Channel, Granularity, OfferSortBy, SortOrder


class Products(SyncResource):
    """Catalogue, departments, brands, lookup by EAN, price history and coverage."""

    def catalog(
        self,
        *,
        search: str | None = None,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        channel: Channel | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> CatalogPage:
        """The catalogue with market statistics per product.

        Cost: 1 unit per page. Beyond page 20 the API requires at least one
        filter and answers :class:`FilterRequiredError` otherwise.

        Args:
            search: Words of the product name, brand or EAN, such as ``"coca cola 2l"``.
            brand: Exact brand, as listed by :meth:`brands`.
            category: Exact category, as listed by :meth:`departments`.
            department: Exact department, as listed by :meth:`departments`.
            state: Two-letter state code.
            channel: ``"e-commerce"`` or ``"delivery"``.
            min_price: Lowest median price.
            max_price: Highest median price.
            page: Page number, from 1.
            limit: Products per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.catalog,
                CatalogPage,
                search=search,
                brand=brand,
                category=category,
                department=department,
                state=state,
                channel=channel,
                min_price=min_price,
                max_price=max_price,
                limit=limit,
            ),
            page=page,
            page_cost_estimate=pricing.query_cost(),
        )

    def departments(self) -> DepartmentsResponse:
        """Departments and their categories, with product counts. Cost: 1 unit.

        The values returned are the ones accepted by the ``department`` and
        ``category`` filters.
        """
        return self._execute(operations.departments())

    def brands(
        self,
        *,
        search: str | None = None,
        department: str | None = None,
        category: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> BrandsPage:
        """Brands of the catalogue. Cost: 1 unit per page.

        Args:
            search: Words of the brand name.
            department: Only brands with products in this department.
            category: Only brands with products in this category.
            page: Page number, from 1.
            limit: Brands per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.brands,
                BrandsPage,
                search=search,
                department=department,
                category=category,
                limit=limit,
            ),
            page=page,
            page_cost_estimate=pricing.query_cost(),
        )

    def by_brand(
        self,
        brand: str,
        *,
        category: str | None = None,
        department: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> ProductsByBrandPage:
        """Products of a brand with their market statistics. Cost: 1 unit per page.

        Args:
            brand: Exact brand, as listed by :meth:`brands`.
            category: Only products in this category.
            department: Only products in this department.
            page: Page number, from 1.
            limit: Products per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.products_by_brand,
                ProductsByBrandPage,
                brand=brand,
                category=category,
                department=department,
                limit=limit,
            ),
            page=page,
            page_cost_estimate=pricing.query_cost(),
        )

    def get(
        self,
        ean: str,
        *,
        state: str | None = None,
        city: str | None = None,
        channel: Channel | None = None,
        sort_by: OfferSortBy = "price",
        sort_order: SortOrder = "asc",
    ) -> Product:
        """A product by EAN: its market statistics and the offer of every store. Cost: 1 unit.

        The first lookup of a product the API has not cached yet can take up to
        90 seconds; afterwards it answers in under a second. A code that is not
        in the catalogue raises :class:`EANNotFoundError` and is not billed.

        Args:
            ean: The product code, 8 or 11 to 14 digits.
            state: Only offers from stores in this state.
            city: Only offers from stores in this city (exact name).
            channel: Only offers from this channel.
            sort_by: Order the offers by price, store name or availability.
            sort_order: ``"asc"`` or ``"desc"``.
        """
        return self._execute(
            operations.product(
                ean,
                state=state,
                city=city,
                channel=channel,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )

    def price_history(
        self,
        ean: str,
        *,
        days: int = 30,
        granularity: Granularity = "daily",
        state: str | None = None,
        store_limit: int = 50,
    ) -> PriceHistory:
        """Price evolution of a product: the market series and one series per store. Cost: 1 unit.

        Args:
            ean: The product code.
            days: Window in days, up to 180.
            granularity: ``"daily"``, ``"weekly"`` or ``"monthly"``.
            state: Only stores in this state, in both series.
            store_limit: Stores in the per-store series, up to 300.
        """
        return self._execute(
            operations.price_history(
                ean, days=days, granularity=granularity, state=state, store_limit=store_limit
            )
        )

    def coverage(self, eans: Sequence[str]) -> CoverageResponse:
        """Which codes of a list the catalogue has. Cost: 1 unit per started block of 250 codes.

        Up to 500 codes per call. Codes that are not valid EANs are counted in
        ``summary.invalid_count`` rather than rejected.
        """
        return self._execute(operations.coverage(eans))


class AsyncProducts(AsyncResource):
    """Catalogue, departments, brands, lookup by EAN, price history and coverage."""

    async def catalog(
        self,
        *,
        search: str | None = None,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        channel: Channel | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> AsyncCatalogPage:
        """The catalogue with market statistics per product. See :meth:`Products.catalog`."""
        return await self._execute_paginated(
            partial(
                operations.catalog,
                AsyncCatalogPage,
                search=search,
                brand=brand,
                category=category,
                department=department,
                state=state,
                channel=channel,
                min_price=min_price,
                max_price=max_price,
                limit=limit,
            ),
            page=page,
            page_cost_estimate=pricing.query_cost(),
        )

    async def departments(self) -> DepartmentsResponse:
        """Departments and their categories. See :meth:`Products.departments`."""
        return await self._execute(operations.departments())

    async def brands(
        self,
        *,
        search: str | None = None,
        department: str | None = None,
        category: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> AsyncBrandsPage:
        """Brands of the catalogue. See :meth:`Products.brands`."""
        return await self._execute_paginated(
            partial(
                operations.brands,
                AsyncBrandsPage,
                search=search,
                department=department,
                category=category,
                limit=limit,
            ),
            page=page,
            page_cost_estimate=pricing.query_cost(),
        )

    async def by_brand(
        self,
        brand: str,
        *,
        category: str | None = None,
        department: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> AsyncProductsByBrandPage:
        """Products of a brand. See :meth:`Products.by_brand`."""
        return await self._execute_paginated(
            partial(
                operations.products_by_brand,
                AsyncProductsByBrandPage,
                brand=brand,
                category=category,
                department=department,
                limit=limit,
            ),
            page=page,
            page_cost_estimate=pricing.query_cost(),
        )

    async def get(
        self,
        ean: str,
        *,
        state: str | None = None,
        city: str | None = None,
        channel: Channel | None = None,
        sort_by: OfferSortBy = "price",
        sort_order: SortOrder = "asc",
    ) -> Product:
        """A product by EAN. See :meth:`Products.get`."""
        return await self._execute(
            operations.product(
                ean,
                state=state,
                city=city,
                channel=channel,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )

    async def price_history(
        self,
        ean: str,
        *,
        days: int = 30,
        granularity: Granularity = "daily",
        state: str | None = None,
        store_limit: int = 50,
    ) -> PriceHistory:
        """Price evolution of a product. See :meth:`Products.price_history`."""
        return await self._execute(
            operations.price_history(
                ean, days=days, granularity=granularity, state=state, store_limit=store_limit
            )
        )

    async def coverage(self, eans: Sequence[str]) -> CoverageResponse:
        """Which codes of a list the catalogue has. See :meth:`Products.coverage`."""
        return await self._execute(operations.coverage(eans))
