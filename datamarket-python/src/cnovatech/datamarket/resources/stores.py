"""Stores: listing, lookup by name, assortment, competitors and price analyses."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from cnovatech.datamarket.errors import AmbiguousStoreError, StoreNotFoundError
from cnovatech.datamarket.models.stores import (
    AssortmentPage,
    AsyncAssortmentPage,
    AsyncComparisonPage,
    AsyncMarketPositionPage,
    AsyncOpportunitiesPage,
    AsyncStoresPage,
    ComparisonPage,
    MarketPositionPage,
    OpportunitiesPage,
    StoresPage,
)
from cnovatech.datamarket.resources import _operations as operations
from cnovatech.sdk_core.resource import AsyncResource, SyncResource

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cnovatech.datamarket.models.stores import (
        CompetitivenessResponse,
        CompetitorsResponse,
        Store,
    )
    from cnovatech.datamarket.types import (
        Channel,
        ComparisonSortBy,
        MarketScope,
        OpportunityType,
        PricePosition,
        SortOrder,
    )

FIND_PAGE_SIZE = 100
# Pages a lookup by name may read before giving up on an exact match.
FIND_MAX_PAGES = 5


def exact_matches(name: str, stores: Sequence[Store]) -> list[Store]:
    """The stores whose name equals ``name``, ignoring case and surrounding spaces."""
    wanted = name.strip().casefold()
    return [store for store in stores if store.store_name.strip().casefold() == wanted]


def select_store(name: str, candidates: Sequence[Store]) -> Store:
    """Pick the store a name refers to among the stores a search returned.

    An exact match on the name, ignoring case, wins over partial matches. With
    no exact match, a single candidate is accepted; none raises
    :class:`StoreNotFoundError` and several raise :class:`AmbiguousStoreError`.
    """
    exact = exact_matches(name, candidates)
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise StoreNotFoundError(
            status_code=404,
            code="store_not_found",
            message=f"No monitored store matches {name!r}.",
            hint="Search with client.stores.list(search=...) to see the names the API knows.",
        )
    raise AmbiguousStoreError(name, exact or candidates)


class Stores(SyncResource):
    """Listing, lookup by name, assortment, competitors and price analyses of stores."""

    def list(
        self,
        *,
        search: str | None = None,
        state: str | None = None,
        city: str | None = None,
        channel: Channel | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> StoresPage:
        """Monitored stores. Cost: 1 unit per page.

        Args:
            search: Words of the store name.
            state: Two-letter state code.
            city: Exact city name, case-insensitive.
            channel: ``"e-commerce"`` or ``"delivery"``.
            page: Page number, from 1.
            limit: Stores per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.stores,
                StoresPage,
                search=search,
                state=state,
                city=city,
                channel=channel,
                limit=limit,
            ),
            page=page,
        )

    def find(self, name: str, *, state: str | None = None, city: str | None = None) -> Store:
        """One store by name. Cost: 1 unit per page searched, usually one.

        An exact name, ignoring case, wins over partial matches. The search
        reads up to five pages of 100 results until it finds an exact match.
        Raises :class:`StoreNotFoundError` when nothing matches and
        :class:`AmbiguousStoreError`, with the candidates, when several stores
        match and none exactly. ``state`` and ``city`` narrow the search.
        """
        first = self.list(search=name, state=state, city=city, limit=FIND_PAGE_SIZE)
        candidates: list[Store] = []
        for page in first.iter_pages(max_pages=FIND_MAX_PAGES - 1):
            candidates.extend(page.data)
            if exact_matches(name, page.data):
                break
        return select_store(name, candidates)

    def assortment(self, store_id: str, *, page: int = 1, limit: int = 100) -> AssortmentPage:
        """The products a store sells, with price and conditions at the last collection.

        Cost: 2 units per started block of 250 rows, per page (``limit=100``
        costs 2, ``limit=1000`` costs 8).

        Args:
            store_id: Identifier from :meth:`list` or :meth:`find`.
            page: Page number, from 1.
            limit: Products per page, up to 1000.
        """
        return self._execute_paginated(
            partial(operations.assortment, AssortmentPage, store_id=store_id, limit=limit),
            page=page,
        )

    def competitors(
        self, store_id: str, *, min_overlap_pct: float = 10.0, limit: int = 10
    ) -> CompetitorsResponse:
        """Stores with the largest assortment overlap. Cost: 1 unit per competitor returned.

        ``limit`` caps both the result and the cost. The first call for a store
        can take about 30 seconds.

        Args:
            store_id: Identifier from :meth:`list` or :meth:`find`.
            min_overlap_pct: Smallest share of assortment in common to count as a competitor.
            limit: Competitors returned, up to 50.
        """
        return self._execute(
            operations.competitors(store_id, min_overlap_pct=min_overlap_pct, limit=limit)
        )

    def competitiveness(
        self,
        store_id: str,
        *,
        min_overlap_pct: float = 5.0,
        limit: int = 20,
        market_scope: MarketScope = "all",
        state: str | None = None,
    ) -> CompetitivenessResponse:
        """Price position of a store against each competitor, as a 0 to 100 score.

        Cost: 1 unit per competitor returned; ``limit`` caps it.

        Args:
            store_id: Identifier from :meth:`list` or :meth:`find`.
            min_overlap_pct: Smallest share of assortment in common to count as a competitor.
            limit: Competitors returned, up to 200.
            market_scope: ``"all"``, ``"same_state"`` or ``"neighbors"``.
            state: Only competitors in this state.
        """
        return self._execute(
            operations.competitiveness(
                store_id,
                min_overlap_pct=min_overlap_pct,
                limit=limit,
                market_scope=market_scope,
                state=state,
            )
        )

    def compare(
        self,
        store_id: str,
        competitor_id: str,
        *,
        price_position: PricePosition = "all",
        search: str | None = None,
        sort_by: ComparisonSortBy = "price_diff_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> ComparisonPage:
        """Product by product against one competitor.

        Cost: 2 units per started block of 250 rows, per page (``limit`` up to
        100 costs 2).

        Args:
            store_id: Identifier of the store.
            competitor_id: Identifier of the competitor, from :meth:`competitors`.
            price_position: Keep only ``"below"``, ``"aligned"``, ``"above"`` or ``"unavailable"``.
            search: Words of the product name, brand or EAN.
            sort_by: Order by price difference, product name or category.
            sort_order: ``"asc"`` or ``"desc"``.
            page: Page number, from 1.
            limit: Products per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.comparison,
                ComparisonPage,
                store_id=store_id,
                competitor_id=competitor_id,
                price_position=price_position,
                search=search,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    def market_position(
        self,
        store_id: str,
        *,
        market_scope: MarketScope = "all",
        state: str | None = None,
        page: int = 1,
        limit: int = 1000,
    ) -> MarketPositionPage:
        """Every product of the store against the market median.

        Cost: 2 units per started block of 250 rows, per page (``limit=1000``
        costs 8).

        Args:
            store_id: Identifier from :meth:`list` or :meth:`find`.
            market_scope: ``"all"``, ``"same_state"`` or ``"neighbors"``.
            state: Only the market of this state.
            page: Page number, from 1.
            limit: Products per page, up to 10000.
        """
        return self._execute_paginated(
            partial(
                operations.market_position,
                MarketPositionPage,
                store_id=store_id,
                market_scope=market_scope,
                state=state,
                limit=limit,
            ),
            page=page,
        )

    def opportunities(
        self,
        store_id: str,
        *,
        opportunity_type: OpportunityType | None = None,
        min_diff_pct: float = 15.0,
        max_diff_pct: float = 100.0,
        min_store_count: int = 3,
        state: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> OpportunitiesPage:
        """What to reprice, by difference against the market median.

        Cost: 2 units per started block of 250 rows, per page (``limit=50``
        costs 2).

        Args:
            store_id: Identifier from :meth:`list` or :meth:`find`.
            opportunity_type: Keep only ``"increase"``, ``"decrease"`` or ``"comfortable"``.
            min_diff_pct: Smallest difference against the median to count as an opportunity.
            max_diff_pct: Largest difference considered, to leave outliers out.
            min_store_count: Other stores that must carry the product for a comparison.
            state: Only the market of this state.
            page: Page number, from 1.
            limit: Products per page, up to 1000.
        """
        return self._execute_paginated(
            partial(
                operations.opportunities,
                OpportunitiesPage,
                store_id=store_id,
                opportunity_type=opportunity_type,
                min_diff_pct=min_diff_pct,
                max_diff_pct=max_diff_pct,
                min_store_count=min_store_count,
                state=state,
                limit=limit,
            ),
            page=page,
        )


class AsyncStores(AsyncResource):
    """Listing, lookup by name, assortment, competitors and price analyses of stores."""

    async def list(
        self,
        *,
        search: str | None = None,
        state: str | None = None,
        city: str | None = None,
        channel: Channel | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> AsyncStoresPage:
        """Monitored stores. See :meth:`Stores.list`."""
        return await self._execute_paginated(
            partial(
                operations.stores,
                AsyncStoresPage,
                search=search,
                state=state,
                city=city,
                channel=channel,
                limit=limit,
            ),
            page=page,
        )

    async def find(self, name: str, *, state: str | None = None, city: str | None = None) -> Store:
        """One store by name. See :meth:`Stores.find`."""
        first = await self.list(search=name, state=state, city=city, limit=FIND_PAGE_SIZE)
        candidates: list[Store] = []
        async for page in first.iter_pages(max_pages=FIND_MAX_PAGES - 1):
            candidates.extend(page.data)
            if exact_matches(name, page.data):
                break
        return select_store(name, candidates)

    async def assortment(
        self, store_id: str, *, page: int = 1, limit: int = 100
    ) -> AsyncAssortmentPage:
        """The products a store sells. See :meth:`Stores.assortment`."""
        return await self._execute_paginated(
            partial(operations.assortment, AsyncAssortmentPage, store_id=store_id, limit=limit),
            page=page,
        )

    async def competitors(
        self, store_id: str, *, min_overlap_pct: float = 10.0, limit: int = 10
    ) -> CompetitorsResponse:
        """Stores with the largest assortment overlap. See :meth:`Stores.competitors`."""
        return await self._execute(
            operations.competitors(store_id, min_overlap_pct=min_overlap_pct, limit=limit)
        )

    async def competitiveness(
        self,
        store_id: str,
        *,
        min_overlap_pct: float = 5.0,
        limit: int = 20,
        market_scope: MarketScope = "all",
        state: str | None = None,
    ) -> CompetitivenessResponse:
        """Price position against each competitor. See :meth:`Stores.competitiveness`."""
        return await self._execute(
            operations.competitiveness(
                store_id,
                min_overlap_pct=min_overlap_pct,
                limit=limit,
                market_scope=market_scope,
                state=state,
            )
        )

    async def compare(
        self,
        store_id: str,
        competitor_id: str,
        *,
        price_position: PricePosition = "all",
        search: str | None = None,
        sort_by: ComparisonSortBy = "price_diff_pct",
        sort_order: SortOrder = "desc",
        page: int = 1,
        limit: int = 50,
    ) -> AsyncComparisonPage:
        """Product by product against one competitor. See :meth:`Stores.compare`."""
        return await self._execute_paginated(
            partial(
                operations.comparison,
                AsyncComparisonPage,
                store_id=store_id,
                competitor_id=competitor_id,
                price_position=price_position,
                search=search,
                sort_by=sort_by,
                sort_order=sort_order,
                limit=limit,
            ),
            page=page,
        )

    async def market_position(
        self,
        store_id: str,
        *,
        market_scope: MarketScope = "all",
        state: str | None = None,
        page: int = 1,
        limit: int = 1000,
    ) -> AsyncMarketPositionPage:
        """Every product of the store against the market median. See :meth:`Stores.market_position`."""
        return await self._execute_paginated(
            partial(
                operations.market_position,
                AsyncMarketPositionPage,
                store_id=store_id,
                market_scope=market_scope,
                state=state,
                limit=limit,
            ),
            page=page,
        )

    async def opportunities(
        self,
        store_id: str,
        *,
        opportunity_type: OpportunityType | None = None,
        min_diff_pct: float = 15.0,
        max_diff_pct: float = 100.0,
        min_store_count: int = 3,
        state: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> AsyncOpportunitiesPage:
        """What to reprice. See :meth:`Stores.opportunities`."""
        return await self._execute_paginated(
            partial(
                operations.opportunities,
                AsyncOpportunitiesPage,
                store_id=store_id,
                opportunity_type=opportunity_type,
                min_diff_pct=min_diff_pct,
                max_diff_pct=max_diff_pct,
                min_store_count=min_store_count,
                state=state,
                limit=limit,
            ),
            page=page,
        )
