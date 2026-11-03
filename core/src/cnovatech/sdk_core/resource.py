"""What every resource shares: a transport and the way to fetch paginated results.

A product SDK groups its endpoints into resources that subclass these two
classes; each method builds an :class:`Operation` and hands it over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeVar

from .pagination import AsyncPage, SyncPage

if TYPE_CHECKING:
    from collections.abc import Callable

    from .operation import Operation
    from .transport import AsyncTransport, SyncTransport

ResultT = TypeVar("ResultT")
SyncPageT = TypeVar("SyncPageT", bound=SyncPage[Any])
AsyncPageT = TypeVar("AsyncPageT", bound=AsyncPage[Any])


class SyncResource:
    """A group of endpoints served through a blocking transport."""

    def __init__(self, transport: SyncTransport) -> None:
        self._transport = transport

    def _execute(self, operation: Operation[ResultT]) -> ResultT:
        return self._transport.execute(operation)

    def _execute_paginated(
        self, build: Callable[..., Operation[SyncPageT]], *, page: int
    ) -> SyncPageT:
        """Fetch ``page`` and give it the means to fetch the pages after it.

        ``build`` receives ``page=`` and returns the operation for that page,
        validated and with its cost estimate, which becomes the page's.
        """

        def fetch(page_number: int) -> SyncPageT:
            operation = build(page=page_number)
            result = self._transport.execute(operation)
            result.attach_pagination(fetch, page_cost_estimate=operation.estimated_cost)
            return result

        return fetch(page)


class AsyncResource:
    """A group of endpoints served through an asynchronous transport."""

    def __init__(self, transport: AsyncTransport) -> None:
        self._transport = transport

    async def _execute(self, operation: Operation[ResultT]) -> ResultT:
        return await self._transport.execute(operation)

    async def _execute_paginated(
        self, build: Callable[..., Operation[AsyncPageT]], *, page: int
    ) -> AsyncPageT:
        """Fetch ``page`` and give it the means to fetch the pages after it."""

        async def fetch(page_number: int) -> AsyncPageT:
            operation = build(page=page_number)
            result = await self._transport.execute(operation)
            result.attach_pagination(fetch, page_cost_estimate=operation.estimated_cost)
            return result

        return await fetch(page)
