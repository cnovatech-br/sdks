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
from cnovatech.datamarket.models.trends import (
    AsyncPriceChangesPage,
    AsyncProductPriceChangesPage,
    AsyncProductPromotionsPage,
    AsyncProductStockoutsPage,
    AsyncPromotionsPage,
    AsyncStockoutsPage,
    PriceChangesPage,
    ProductPriceChangesPage,
    ProductPromotionsPage,
    ProductStockoutsPage,
    PromotionsPage,
    StockoutsPage,
)
from cnovatech.datamarket.resources import _operations as operations
from cnovatech.sdk_core.resource import AsyncResource, SyncResource

if TYPE_CHECKING:
    from collections.abc import Iterable

    from cnovatech.datamarket.models.history import PriceHistory
    from cnovatech.datamarket.models.products import (
        CoverageResponse,
        DepartmentsResponse,
        Product,
    )
    from cnovatech.datamarket.types import (
        CatalogSortBy,
        Channel,
        Granularity,
        OfferSortBy,
        PriceChangeSortBy,
        PromotionSortBy,
        SortOrder,
        StockoutSortBy,
        TrendWindow,
    )


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
        min_store_count: int | None = None,
        sort_by: CatalogSortBy | None = None,
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> CatalogPage:
        """The catalogue with market statistics per product.

        Cost: 1 unit per page. Beyond page 20 the API requires at least one
        filter and answers :class:`FilterRequiredError` otherwise.

        Without ``sort_by`` the products come by number of stores, or by
        similarity when ``search`` is given. The statistics of each product
        are nationwide even with ``state``; that filter adds
        ``state_store_count``, the stores of the state selling the product,
        and ``sort_by="state_store_count"`` orders by it.

        Args:
            search: Words of the product name, brand or EAN, such as ``"coca cola 2l"``.
            brand: Exact brand, as listed by :meth:`brands`.
            category: Exact category, as listed by :meth:`departments`.
            department: Exact department, as listed by :meth:`departments`.
            state: Two-letter state code.
            channel: ``"e-commerce"`` or ``"delivery"``.
            min_price: Lowest median price.
            max_price: Highest median price.
            min_store_count: Only products sold by at least this many stores.
            sort_by: Field to order by; ``"state_store_count"`` needs ``state``.
            sort_order: ``"asc"`` or ``"desc"``, used with ``sort_by``.
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
                min_store_count=min_store_count,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
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
            ean: The product code: 8, 11, 12, 13 or 14 digits, the lengths the
                catalogue carries. Other lengths are refused before sending.
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

    def coverage(self, eans: Iterable[str]) -> CoverageResponse:
        """Which codes of a list the catalogue has. Cost: 1 unit per started block of 250 codes.

        Up to 500 codes per call, from any iterable of strings. Codes that are
        not valid EANs are counted in ``summary.invalid_count`` rather than
        rejected.
        """
        return self._execute(operations.coverage(eans))

    def price_changes(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        search: str | None = None,
        days: TrendWindow = 30,
        min_store_count: int = 5,
        sort_by: PriceChangeSortBy = "repriced_store_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> PriceChangesPage:
        """Ranking of the products whose price changed in the window.

        Cost: 1 unit per page. Beyond page 20 the API requires at least one
        filter and answers :class:`FilterRequiredError` otherwise.

        Ordered by the share of stores that repriced, since a total only
        follows how widely a product is distributed. ``price_change_count``
        is a floor: stores are collected in rotation and only a change seen
        between two collections is counted. For the stores behind a row, see
        :meth:`price_change_detail`.

        Args:
            brand: Exact brand, as listed by :meth:`brands`.
            category: Exact category, as listed by :meth:`departments`.
            department: Exact department, as listed by :meth:`departments`.
            state: Two-letter state code; counts and shares become the state's.
            search: Words of the product name, brand or EAN.
            days: Window in days: 30 or 90.
            min_store_count: Stores that must sell the product for it to enter.
            sort_by: Field to order by.
            sort_order: ``"asc"`` or ``"desc"``.
            page: Page number, from 1.
            limit: Products per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.price_changes,
                PriceChangesPage,
                days=days,
                brand=brand,
                category=category,
                department=department,
                state=state,
                search=search,
                min_store_count=min_store_count,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    def promotions(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        search: str | None = None,
        days: TrendWindow = 30,
        min_store_count: int = 5,
        min_discount_pct: float | None = None,
        sort_by: PromotionSortBy = "promo_store_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> PromotionsPage:
        """Ranking of the products stores advertised on promotion in the window.

        Cost: 1 unit per page. Beyond page 20 the API requires at least one
        filter and answers :class:`FilterRequiredError` otherwise.

        A promotion is the store itself showing a list price above its sale
        price. Ordered by the share of stores promoting. For the stores
        behind a row, see :meth:`promotion_detail`.

        Args:
            brand: Exact brand, as listed by :meth:`brands`.
            category: Exact category, as listed by :meth:`departments`.
            department: Exact department, as listed by :meth:`departments`.
            state: Two-letter state code; counts and shares become the state's.
            search: Words of the product name, brand or EAN.
            days: Window in days: 30 or 90.
            min_store_count: Stores that must sell the product for it to enter.
            min_discount_pct: Smallest typical discount, up to 70.
            sort_by: Field to order by.
            sort_order: ``"asc"`` or ``"desc"``.
            page: Page number, from 1.
            limit: Products per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.promotions,
                PromotionsPage,
                days=days,
                brand=brand,
                category=category,
                department=department,
                state=state,
                search=search,
                min_store_count=min_store_count,
                min_discount_pct=min_discount_pct,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    def stockouts(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        search: str | None = None,
        days: TrendWindow = 30,
        min_store_count: int = 5,
        sort_by: StockoutSortBy = "stockout_store_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> StockoutsPage:
        """Ranking of the products that are out of stock, by share of stores affected.

        Cost: 1 unit per page. Beyond page 20 the API requires at least one
        filter and answers :class:`FilterRequiredError` otherwise.

        A stockout is a store that sold the product in the window and has it
        unavailable now. A listing that was never available in the window is
        a product the store stopped selling and does not count. For the
        stores behind a row, see :meth:`stockout_detail`.

        Args:
            brand: Exact brand, as listed by :meth:`brands`.
            category: Exact category, as listed by :meth:`departments`.
            department: Exact department, as listed by :meth:`departments`.
            state: Two-letter state code; counts and shares become the state's.
            search: Words of the product name, brand or EAN.
            days: Window in days: 30 or 90.
            min_store_count: Stores that must sell the product for it to enter.
            sort_by: Field to order by.
            sort_order: ``"asc"`` or ``"desc"``.
            page: Page number, from 1.
            limit: Products per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.stockouts,
                StockoutsPage,
                days=days,
                brand=brand,
                category=category,
                department=department,
                state=state,
                search=search,
                min_store_count=min_store_count,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    def price_change_detail(
        self,
        ean: str,
        *,
        days: TrendWindow = 30,
        state: str | None = None,
        min_price_change_count: int = 0,
        page: int = 1,
        limit: int = 100,
    ) -> ProductPriceChangesPage:
        """What happened to the price of a product, store by store.

        Cost: 1 unit per page of stores.

        Each store carries its current price, its distance from the median
        of the stores and ``changes``: the day each new price was seen, the
        previous price and the new one. ``summary`` and ``by_state`` describe
        every store, whatever the page or the filter. A code that is not in
        the catalogue raises :class:`EANNotFoundError` and is not billed.

        Args:
            ean: The product code.
            days: Window in days: 30 or 90.
            state: Only stores in this state.
            min_price_change_count: Only stores with at least this many
                changes; 1 keeps the ones that changed the price.
            page: Page number, from 1.
            limit: Stores per page, up to 300.
        """
        return self._execute_paginated(
            partial(
                operations.product_price_changes,
                ProductPriceChangesPage,
                ean=ean,
                days=days,
                state=state,
                min_price_change_count=min_price_change_count,
                limit=limit,
            ),
            page=page,
        )

    def promotion_detail(
        self,
        ean: str,
        *,
        days: TrendWindow = 30,
        state: str | None = None,
        on_promotion: bool | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> ProductPromotionsPage:
        """The promotions of a product, store by store.

        Cost: 1 unit per page of stores.

        Each store that promoted the product carries its latest list price,
        sale price and discount, its discount range and ``periods``: each
        stretch on promotion with the first and the last day it was seen.
        ``summary``, ``by_day`` and ``by_state`` describe every store. A code
        that is not in the catalogue raises :class:`EANNotFoundError` and is
        not billed.

        Args:
            ean: The product code.
            days: Window in days: 30 or 90.
            state: Only stores in this state.
            on_promotion: ``True`` for the stores on promotion now, ``False``
                for the ones whose promotion ended.
            page: Page number, from 1.
            limit: Stores per page, up to 300.
        """
        return self._execute_paginated(
            partial(
                operations.product_promotions,
                ProductPromotionsPage,
                ean=ean,
                days=days,
                state=state,
                on_promotion=on_promotion,
                limit=limit,
            ),
            page=page,
        )

    def stockout_detail(
        self,
        ean: str,
        *,
        days: TrendWindow = 30,
        state: str | None = None,
        available: bool | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> ProductStockoutsPage:
        """Where a product is out of stock, store by store, and since when.

        Cost: 1 unit per page of stores.

        Each store carries its availability now, the day the current gap was
        first seen, the days without the product and ``periods``: each gap
        in the window. ``summary``, ``by_day`` and ``by_state`` describe
        every store; ``summary.never_available_store_count`` is the stores
        that list the product without ever having had it in the window. A
        code that is not in the catalogue raises :class:`EANNotFoundError`
        and is not billed.

        Args:
            ean: The product code.
            days: Window in days: 30 or 90.
            state: Only stores in this state.
            available: ``False`` for the stores out of stock, ``True`` for
                the ones that have the product.
            page: Page number, from 1.
            limit: Stores per page, up to 300.
        """
        return self._execute_paginated(
            partial(
                operations.product_stockouts,
                ProductStockoutsPage,
                ean=ean,
                days=days,
                state=state,
                available=available,
                limit=limit,
            ),
            page=page,
        )


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
        min_store_count: int | None = None,
        sort_by: CatalogSortBy | None = None,
        sort_order: SortOrder = "desc",
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
                min_store_count=min_store_count,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
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

    async def coverage(self, eans: Iterable[str]) -> CoverageResponse:
        """Which codes of a list the catalogue has. See :meth:`Products.coverage`."""
        return await self._execute(operations.coverage(eans))

    async def price_changes(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        search: str | None = None,
        days: TrendWindow = 30,
        min_store_count: int = 5,
        sort_by: PriceChangeSortBy = "repriced_store_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> AsyncPriceChangesPage:
        """Ranking of the products whose price changed. See :meth:`Products.price_changes`."""
        return await self._execute_paginated(
            partial(
                operations.price_changes,
                AsyncPriceChangesPage,
                days=days,
                brand=brand,
                category=category,
                department=department,
                state=state,
                search=search,
                min_store_count=min_store_count,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    async def promotions(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        search: str | None = None,
        days: TrendWindow = 30,
        min_store_count: int = 5,
        min_discount_pct: float | None = None,
        sort_by: PromotionSortBy = "promo_store_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> AsyncPromotionsPage:
        """Ranking of the products on promotion. See :meth:`Products.promotions`."""
        return await self._execute_paginated(
            partial(
                operations.promotions,
                AsyncPromotionsPage,
                days=days,
                brand=brand,
                category=category,
                department=department,
                state=state,
                search=search,
                min_store_count=min_store_count,
                min_discount_pct=min_discount_pct,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    async def stockouts(
        self,
        *,
        brand: str | None = None,
        category: str | None = None,
        department: str | None = None,
        state: str | None = None,
        search: str | None = None,
        days: TrendWindow = 30,
        min_store_count: int = 5,
        sort_by: StockoutSortBy = "stockout_store_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> AsyncStockoutsPage:
        """Ranking of the products out of stock. See :meth:`Products.stockouts`."""
        return await self._execute_paginated(
            partial(
                operations.stockouts,
                AsyncStockoutsPage,
                days=days,
                brand=brand,
                category=category,
                department=department,
                state=state,
                search=search,
                min_store_count=min_store_count,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    async def price_change_detail(
        self,
        ean: str,
        *,
        days: TrendWindow = 30,
        state: str | None = None,
        min_price_change_count: int = 0,
        page: int = 1,
        limit: int = 100,
    ) -> AsyncProductPriceChangesPage:
        """Price changes of a product, store by store. See :meth:`Products.price_change_detail`."""
        return await self._execute_paginated(
            partial(
                operations.product_price_changes,
                AsyncProductPriceChangesPage,
                ean=ean,
                days=days,
                state=state,
                min_price_change_count=min_price_change_count,
                limit=limit,
            ),
            page=page,
        )

    async def promotion_detail(
        self,
        ean: str,
        *,
        days: TrendWindow = 30,
        state: str | None = None,
        on_promotion: bool | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> AsyncProductPromotionsPage:
        """Promotions of a product, store by store. See :meth:`Products.promotion_detail`."""
        return await self._execute_paginated(
            partial(
                operations.product_promotions,
                AsyncProductPromotionsPage,
                ean=ean,
                days=days,
                state=state,
                on_promotion=on_promotion,
                limit=limit,
            ),
            page=page,
        )

    async def stockout_detail(
        self,
        ean: str,
        *,
        days: TrendWindow = 30,
        state: str | None = None,
        available: bool | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> AsyncProductStockoutsPage:
        """Stockouts of a product, store by store. See :meth:`Products.stockout_detail`."""
        return await self._execute_paginated(
            partial(
                operations.product_stockouts,
                AsyncProductStockoutsPage,
                ean=ean,
                days=days,
                state=state,
                available=available,
                limit=limit,
            ),
            page=page,
        )
