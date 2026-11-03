"""Brands: where a brand is sold."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cnovatech.datamarket.resources import _operations as operations
from cnovatech.sdk_core.resource import AsyncResource, SyncResource

if TYPE_CHECKING:
    from cnovatech.datamarket.models.brands import StoresByBrandResponse
    from cnovatech.datamarket.types import Channel


class Brands(SyncResource):
    """Where a brand is sold."""

    def stores(
        self,
        brand: str,
        *,
        state: str | None = None,
        channel: Channel | None = None,
        min_product_count: int = 1,
    ) -> StoresByBrandResponse:
        """Stores that sell the brand, with its price and availability in each. Cost: 1 unit.

        Args:
            brand: Exact brand, as listed by ``products.brands()``.
            state: Only stores in this state.
            channel: ``"e-commerce"`` or ``"delivery"``.
            min_product_count: Smallest number of the brand's products a store must sell.
        """
        return self._execute(
            operations.stores_by_brand(
                brand, state=state, channel=channel, min_product_count=min_product_count
            )
        )


class AsyncBrands(AsyncResource):
    """Where a brand is sold."""

    async def stores(
        self,
        brand: str,
        *,
        state: str | None = None,
        channel: Channel | None = None,
        min_product_count: int = 1,
    ) -> StoresByBrandResponse:
        """Stores that sell the brand. See :meth:`Brands.stores`."""
        return await self._execute(
            operations.stores_by_brand(
                brand, state=state, channel=channel, min_product_count=min_product_count
            )
        )
