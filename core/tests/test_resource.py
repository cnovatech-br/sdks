"""The resource bases: executing operations and wiring pages to the pages after them."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, TypeVar

import httpx
from conftest import Thing, thing_operation
from pydantic import BaseModel

from cnovatech.sdk_core.operation import Operation
from cnovatech.sdk_core.pagination import AsyncPage, SyncPage
from cnovatech.sdk_core.resource import AsyncResource, SyncResource

if TYPE_CHECKING:
    from collections.abc import Callable

    from cnovatech.sdk_core.transport import AsyncTransport, SyncTransport

PageT = TypeVar("PageT", bound=BaseModel)


class ThingsPage(SyncPage[Thing]):
    pass


class AsyncThingsPage(AsyncPage[Thing]):
    pass


def things_operation(page_model: type[PageT], *, limit: int, page: int) -> Operation[PageT]:
    return Operation(
        method="GET",
        path="/things",
        parse=page_model.model_validate,
        params={"page": page, "limit": limit},
        estimated_cost=3,
    )


class Things(SyncResource):
    def get(self) -> Thing:
        return self._execute(thing_operation())

    def list(self, *, page: int = 1, limit: int = 2) -> ThingsPage:
        return self._execute_paginated(
            partial(things_operation, ThingsPage, limit=limit), page=page
        )


class AsyncThings(AsyncResource):
    async def get(self) -> Thing:
        return await self._execute(thing_operation())

    async def list(self, *, page: int = 1, limit: int = 2) -> AsyncThingsPage:
        return await self._execute_paginated(
            partial(things_operation, AsyncThingsPage, limit=limit), page=page
        )


def pages_handler(request: httpx.Request) -> httpx.Response:
    """Serve three pages of two things each, or a single thing for any other path."""
    if request.url.path.endswith("/things/1"):
        return httpx.Response(200, json={"identifier": "1", "name": "Milk"})
    page = int(request.url.params["page"])
    return httpx.Response(
        200,
        json={
            "data": [{"identifier": f"{page}-{index}", "name": "Milk"} for index in range(2)],
            "meta": {"page": page, "limit": 2, "total": 6, "pages": 3},
            "usage": {"query_cost": 3},
        },
    )


def test_resource_executes_single_operations(
    make_sync_transport: Callable[..., SyncTransport],
) -> None:
    things = Things(make_sync_transport(pages_handler))

    assert things.get().identifier == "1"


def test_pages_know_their_cost_and_how_to_continue(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    things = Things(make_sync_transport(pages_handler))

    first = things.list(limit=2)
    identifiers = [thing.identifier for thing in first.iter_all()]

    assert first.page_cost_estimate == 3
    assert first.estimate_remaining_cost() == 6
    assert identifiers == ["1-0", "1-1", "2-0", "2-1", "3-0", "3-1"]
    assert [dict(request.url.params) for request in sent_requests] == [
        {"page": "1", "limit": "2"},
        {"page": "2", "limit": "2"},
        {"page": "3", "limit": "2"},
    ]


async def test_async_resource_mirrors_the_synchronous_one(
    make_async_transport: Callable[..., AsyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    things = AsyncThings(make_async_transport(pages_handler))

    thing = await things.get()
    first = await things.list(limit=2)
    identifiers = [item.identifier async for item in first.iter_all(max_pages=1)]

    assert thing.identifier == "1"
    assert first.page_cost_estimate == 3
    assert identifiers == ["1-0", "1-1", "2-0", "2-1"]
    assert len(sent_requests) == 3
