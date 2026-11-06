"""Synchronous and asynchronous clients for the Data Market API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cnovatech.sdk_core.client import BaseAsyncClient, BaseSyncClient
from cnovatech.sdk_core.config import DEFAULT_MAX_RETRIES, DEFAULT_READ_TIMEOUT_SECONDS

from ._config import PRODUCT_SETTINGS
from .resources import (
    Account,
    AsyncAccount,
    AsyncBrands,
    AsyncProducts,
    AsyncStores,
    Brands,
    Products,
    Stores,
    _operations as operations,
)

if TYPE_CHECKING:
    import httpx

    from .models import Health

_CONSTRUCTOR_DOC = """
    Args:
        api_key: Key issued by Data Market (``dm_...``). Defaults to the
            ``DATAMARKET_API_KEY`` environment variable. Only ``health()`` works
            without one.
        base_url: Origin of the API. Defaults to ``DATAMARKET_BASE_URL`` or production.
        timeout: Read timeout in seconds, or an ``httpx.Timeout`` to set every
            phase. The default of 150 s covers the first lookup of an uncached
            product, which can take about 90 s. It applies to every request,
            also through your own ``http_client``.
        max_retries: Extra attempts for failures that cannot have been billed:
            connection errors, 502/503 and the per-minute 429. Read timeouts,
            504 and quota errors are never retried.
        max_units_per_request: Refuse, before sending, any call estimated to
            cost more than this many quota units. Off by default.
        http_client: Your own httpx client, for proxies, certificates or a
            shared connection pool. The SDK does not close it and never follows
            redirects through it, whatever its own settings.
        transport: An httpx transport, used by tests to answer without a network.

    The client keeps a connection pool: create one per process and close it
    with ``close()`` or a ``with`` block. It can be shared between threads;
    the ``usage`` counters are updated without a lock and may lag under heavy
    concurrency. Responses, pages and exceptions can be pickled; a page
    restored from a pickle cannot fetch the pages after it.
"""


class DataMarket(BaseSyncClient):
    """Client for the Data Market API using blocking I/O.

    Attributes:
        products: Catalogue, departments, brands, lookup by EAN, price history and coverage.
        stores: Listing, lookup by name, assortment, competitors and price analyses.
        brands: Where a brand is sold.
        account: Profile, quota history, request log and API keys.
    """

    __doc__ = (__doc__ or "") + _CONSTRUCTOR_DOC

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = DEFAULT_READ_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_units_per_request: int | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            PRODUCT_SETTINGS,
            api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_units_per_request=max_units_per_request,
            http_client=http_client,
            transport=transport,
        )
        self.products = Products(self._transport)
        self.stores = Stores(self._transport)
        self.brands = Brands(self._transport)
        self.account = Account(self._transport)

    def health(self) -> Health:
        """Check that the API, its database and its cache are up.

        No authentication and no quota cost.
        """
        return self._transport.execute(operations.health())


class AsyncDataMarket(BaseAsyncClient):
    """Client for the Data Market API using asyncio.

    Attributes:
        products: Catalogue, departments, brands, lookup by EAN, price history and coverage.
        stores: Listing, lookup by name, assortment, competitors and price analyses.
        brands: Where a brand is sold.
        account: Profile, quota history, request log and API keys.
    """

    __doc__ = (__doc__ or "") + _CONSTRUCTOR_DOC

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = DEFAULT_READ_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_units_per_request: int | None = None,
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__(
            PRODUCT_SETTINGS,
            api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_units_per_request=max_units_per_request,
            http_client=http_client,
            transport=transport,
        )
        self.products = AsyncProducts(self._transport)
        self.stores = AsyncStores(self._transport)
        self.brands = AsyncBrands(self._transport)
        self.account = AsyncAccount(self._transport)

    async def health(self) -> Health:
        """Check that the API, its database and its cache are up.

        No authentication and no quota cost.
        """
        return await self._transport.execute(operations.health())
