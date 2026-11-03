"""What every product client shares: configuration, transport, accounting and lifecycle.

A product SDK subclasses :class:`BaseSyncClient` and :class:`BaseAsyncClient`,
binds its :class:`ProductSettings` and attaches its resources. Everything
else, from reading the environment to closing the connection pool, is here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .config import DEFAULT_MAX_RETRIES, DEFAULT_READ_TIMEOUT_SECONDS, build_client_config
from .transport import AsyncTransport, SyncTransport

if TYPE_CHECKING:
    from types import TracebackType

    import httpx
    from typing_extensions import Self

    from .config import ProductSettings
    from .usage import RateLimitState, UsageTracker


class BaseSyncClient:
    """A client using blocking I/O. See the product client for the constructor arguments."""

    def __init__(
        self,
        product: ProductSettings,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = DEFAULT_READ_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_units_per_request: int | None = None,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._config = build_client_config(
            product,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_units_per_request=max_units_per_request,
        )
        self._transport = SyncTransport(self._config, http_client=http_client, transport=transport)

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


class BaseAsyncClient:
    """A client using asyncio. See the product client for the constructor arguments."""

    def __init__(
        self,
        product: ProductSettings,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        timeout: float | httpx.Timeout = DEFAULT_READ_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_units_per_request: int | None = None,
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = build_client_config(
            product,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_units_per_request=max_units_per_request,
        )
        self._transport = AsyncTransport(self._config, http_client=http_client, transport=transport)

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
