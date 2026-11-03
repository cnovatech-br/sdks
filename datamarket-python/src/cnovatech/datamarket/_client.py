"""Synchronous and asynchronous clients for the Data Market API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cnovatech.sdk_core.config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_READ_TIMEOUT_SECONDS,
    ClientConfig,
    build_client_config,
)
from cnovatech.sdk_core.transport import AsyncTransport, SyncTransport

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
    from types import TracebackType

    import httpx
    from typing_extensions import Self

    from cnovatech.sdk_core.usage import RateLimitState, UsageTracker

    from .models import Health

_CONSTRUCTOR_DOC = """
    Args:
        api_key: Key issued by Data Market (``dm_...``). Defaults to the
            ``DATAMARKET_API_KEY`` environment variable. Only ``health()`` works
            without one.
        base_url: Origin of the API. Defaults to ``DATAMARKET_BASE_URL`` or production.
        timeout: Read timeout in seconds, or an ``httpx.Timeout`` to set every
            phase. The default of 150 s covers the first lookup of an uncached
            product, which can take about 90 s.
        max_retries: Extra attempts for failures that cannot have been billed:
            connection errors, 502/503 and the per-minute 429. Read timeouts,
            504 and quota errors are never retried.
        max_units_per_request: Refuse, before sending, any call estimated to
            cost more than this many quota units. Off by default.
        http_client: Your own httpx client, for proxies, certificates or a
            shared connection pool. The SDK does not close it.
        transport: An httpx transport, used by tests to answer without a network.

    The client keeps a connection pool: create one per process and close it
    with ``close()`` or a ``with`` block.
"""


def _build_config(
    api_key: str | None,
    base_url: str | None,
    timeout: float | httpx.Timeout,
    max_retries: int,
    max_units_per_request: int | None,
) -> ClientConfig:
    return build_client_config(
        PRODUCT_SETTINGS,
        api_key=api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
        max_units_per_request=max_units_per_request,
    )


class DataMarket:
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
        self._config = _build_config(api_key, base_url, timeout, max_retries, max_units_per_request)
        self._transport = SyncTransport(self._config, http_client=http_client, transport=transport)
        self.products = Products(self._transport)
        self.stores = Stores(self._transport)
        self.brands = Brands(self._transport)
        self.account = Account(self._transport)

    @property
    def base_url(self) -> str:
        """Origin the client talks to."""
        return self._config.base_url

    @property
    def usage(self) -> UsageTracker:
        """Quota spent through this client: ``spent``, ``calls`` and the ``last`` usage block."""
        return self._transport.usage

    @property
    def rate_limit(self) -> RateLimitState:
        """The per-minute rate limit as last reported by the API."""
        return self._transport.rate_limit

    def health(self) -> Health:
        """Check that the API, its database and its cache are up.

        No authentication and no quota cost.
        """
        return self._transport.execute(operations.health())

    def close(self) -> None:
        """Release the connection pool. Clients supplied through ``http_client`` are left open."""
        self._transport.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(base_url={self._config.base_url!r}, "
            f"api_key={self._config.masked_api_key!r})"
        )


class AsyncDataMarket:
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
        self._config = _build_config(api_key, base_url, timeout, max_retries, max_units_per_request)
        self._transport = AsyncTransport(self._config, http_client=http_client, transport=transport)
        self.products = AsyncProducts(self._transport)
        self.stores = AsyncStores(self._transport)
        self.brands = AsyncBrands(self._transport)
        self.account = AsyncAccount(self._transport)

    @property
    def base_url(self) -> str:
        """Origin the client talks to."""
        return self._config.base_url

    @property
    def usage(self) -> UsageTracker:
        """Quota spent through this client: ``spent``, ``calls`` and the ``last`` usage block."""
        return self._transport.usage

    @property
    def rate_limit(self) -> RateLimitState:
        """The per-minute rate limit as last reported by the API."""
        return self._transport.rate_limit

    async def health(self) -> Health:
        """Check that the API, its database and its cache are up.

        No authentication and no quota cost.
        """
        return await self._transport.execute(operations.health())

    async def aclose(self) -> None:
        """Release the connection pool. Clients supplied through ``http_client`` are left open."""
        await self._transport.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(base_url={self._config.base_url!r}, "
            f"api_key={self._config.masked_api_key!r})"
        )
