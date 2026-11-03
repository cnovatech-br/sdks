from __future__ import annotations

from typing import Any

import pytest

from cnovatech.sdk_core.errors import BudgetExceededError
from cnovatech.sdk_core.models import APIResponse
from cnovatech.sdk_core.pagination import AsyncPage, SyncPage


class Item(APIResponse):
    name: str


class Envelope(APIResponse):
    owner: str


class ItemsPage(SyncPage[Item], Envelope):
    pass


class AsyncItemsPage(AsyncPage[Item], Envelope):
    pass


def payload(
    page: int, pages: int, *, names: list[str] | None = None, cost: int = 2
) -> dict[str, Any]:
    items = names if names is not None else [f"item-{page}-{index}" for index in range(2)]
    return {
        "owner": "me",
        "data": [{"name": name} for name in items],
        "meta": {"page": page, "limit": 2, "total": 2 * pages, "pages": pages},
        "usage": {"query_cost": cost, "used": None, "limit": None, "remaining": None},
    }


class FakeResource:
    """Serves pages from a dict and records what was fetched."""

    def __init__(self, pages: dict[int, dict[str, Any]], *, page_cost_estimate: int = 2) -> None:
        self.pages = pages
        self.fetched: list[int] = []
        self.page_cost_estimate = page_cost_estimate

    def fetch(self, page_number: int) -> ItemsPage:
        self.fetched.append(page_number)
        page = ItemsPage.model_validate(self.pages[page_number])
        page.attach_pagination(self.fetch, page_cost_estimate=self.page_cost_estimate)
        return page

    async def fetch_async(self, page_number: int) -> AsyncItemsPage:
        self.fetched.append(page_number)
        page = AsyncItemsPage.model_validate(self.pages[page_number])
        page.attach_pagination(self.fetch_async, page_cost_estimate=self.page_cost_estimate)
        return page


def three_pages() -> FakeResource:
    return FakeResource({1: payload(1, 3), 2: payload(2, 3), 3: payload(3, 3)})


def test_page_keeps_envelope_fields_and_behaves_like_a_list() -> None:
    page = three_pages().fetch(1)

    assert page.owner == "me"
    assert len(page) == 2
    assert [item.name for item in page] == ["item-1-0", "item-1-1"]
    assert page.has_next is True
    assert page.page_cost_estimate == 2
    assert page.estimate_remaining_cost() == 4


def test_last_page_has_no_next() -> None:
    page = three_pages().fetch(3)

    assert page.has_next is False
    assert page.next_page() is None
    assert page.estimate_remaining_cost() == 0


def test_next_page_fetches_the_following_one() -> None:
    resource = three_pages()

    following = resource.fetch(1).next_page()

    assert following is not None
    assert following.meta.page == 2
    assert resource.fetched == [1, 2]


def test_iter_pages_starts_with_the_current_page_without_refetching() -> None:
    resource = three_pages()
    first = resource.fetch(2)

    pages = list(first.iter_pages())

    assert [page.meta.page for page in pages] == [2, 3]
    assert resource.fetched == [2, 3]


def test_iter_all_walks_every_item() -> None:
    resource = three_pages()

    names = [item.name for item in resource.fetch(1).iter_all()]

    assert names == ["item-1-0", "item-1-1", "item-2-0", "item-2-1", "item-3-0", "item-3-1"]


def test_max_pages_counts_new_pages_and_stops_quietly() -> None:
    resource = three_pages()

    pages = list(resource.fetch(1).iter_pages(max_pages=1))

    assert [page.meta.page for page in pages] == [1, 2]
    assert resource.fetched == [1, 2]


def test_max_units_refuses_before_the_page_that_would_cross_it() -> None:
    resource = three_pages()
    first = resource.fetch(1)
    delivered: list[int] = []

    def consume() -> None:
        delivered.extend(page.meta.page for page in first.iter_pages(max_units=3))

    with pytest.raises(BudgetExceededError) as excinfo:
        consume()

    assert delivered == [1, 2]
    assert excinfo.value.spent == 2
    assert excinfo.value.estimated_cost == 2
    assert excinfo.value.limit == 3
    assert excinfo.value.items_yielded == 4
    assert resource.fetched == [1, 2]


def test_max_units_uses_the_real_cost_of_fetched_pages() -> None:
    resource = FakeResource({1: payload(1, 3), 2: payload(2, 3, cost=1), 3: payload(3, 3, cost=1)})

    pages = list(resource.fetch(1).iter_pages(max_units=3))

    assert [page.meta.page for page in pages] == [1, 2, 3]


def test_max_units_zero_yields_only_the_paid_page() -> None:
    first = three_pages().fetch(1)

    with pytest.raises(BudgetExceededError):
        list(first.iter_pages(max_units=0))


def test_an_empty_page_ends_the_iteration() -> None:
    resource = FakeResource({1: payload(1, 3), 2: payload(2, 3, names=[]), 3: payload(3, 3)})

    pages = list(resource.fetch(1).iter_pages())

    assert [page.meta.page for page in pages] == [1]
    assert resource.fetched == [1, 2]


def test_pages_without_usage_spend_nothing_against_the_budget() -> None:
    free = {key: {**value, "usage": None} for key, value in three_pages().pages.items()}
    resource = FakeResource(free)

    pages = list(resource.fetch(1).iter_pages(max_units=2))

    assert [page.meta.page for page in pages] == [1, 2, 3]
    assert pages[0].usage is None


def test_detached_page_cannot_paginate() -> None:
    page = ItemsPage.model_validate(payload(1, 2))

    with pytest.raises(RuntimeError, match="not produced by a client"):
        page.next_page()


def test_to_dataframe_repeats_the_envelope_on_every_row() -> None:
    frame = three_pages().fetch(1).to_dataframe()

    assert list(frame.columns) == [
        "owner",
        "usage_query_cost",
        "usage_used",
        "usage_limit",
        "usage_remaining",
        "name",
    ]
    assert frame["owner"].tolist() == ["me", "me"]
    assert frame["name"].tolist() == ["item-1-0", "item-1-1"]


def test_to_dataframe_without_envelope() -> None:
    frame = three_pages().fetch(1).to_dataframe(include_envelope=False)

    assert list(frame.columns) == ["name"]


async def test_async_iteration_mirrors_the_synchronous_one() -> None:
    resource = three_pages()
    first = await resource.fetch_async(1)

    names = [item.name async for item in first.iter_all(max_pages=1)]
    following = await first.next_page()

    assert names == ["item-1-0", "item-1-1", "item-2-0", "item-2-1"]
    assert following is not None
    assert following.meta.page == 2
    assert resource.fetched == [1, 2, 2]


async def test_async_max_units_refuses_before_sending() -> None:
    resource = three_pages()
    first = await resource.fetch_async(1)

    with pytest.raises(BudgetExceededError):
        async for _ in first.iter_pages(max_units=1):
            pass

    assert resource.fetched == [1]
