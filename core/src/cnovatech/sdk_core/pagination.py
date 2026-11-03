"""Paginated responses that can fetch what follows, with explicit cost control.

A page is a response model like any other, plus the ability to request the
next page through the resource that produced it. Iteration never re-requests
the page already paid for, stops quietly at ``max_pages`` and refuses, before
sending, a page that would cross ``max_units``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import PrivateAttr

from .dataframe import TabularResponse
from .errors import BudgetExceededError
from .models import PaginationMeta, Usage

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

    from typing_extensions import Self

ItemT = TypeVar("ItemT")


class _PageBase(TabularResponse, Generic[ItemT]):
    """What the synchronous and asynchronous pages share."""

    data: list[ItemT]
    meta: PaginationMeta
    usage: Usage | None = None

    _fetch_page: Any = PrivateAttr(default=None)
    _page_cost_estimate: int = PrivateAttr(default=1)

    def __iter__(self) -> Iterator[ItemT]:  # type: ignore[override]
        """Iterate over the items of this page only."""
        return iter(self.data)

    def __len__(self) -> int:
        return len(self.data)

    def __bool__(self) -> bool:
        """A page is always truthy: an empty page is still a complete, billed response."""
        return True

    @property
    def has_next(self) -> bool:
        """Whether the API has a page after this one."""
        return self.meta.page < self.meta.pages

    @property
    def page_cost_estimate(self) -> int:
        """Estimated cost of one full page, used for pages not fetched yet."""
        return self._page_cost_estimate

    def estimate_remaining_cost(self) -> int:
        """Units expected to fetch every page after this one, at the estimated page cost."""
        return max(0, self.meta.pages - self.meta.page) * self._page_cost_estimate

    def _check_budget(self, *, spent: int, max_units: int | None, items_yielded: int) -> None:
        next_cost = self._page_cost_estimate
        if max_units is not None and spent + next_cost > max_units:
            raise BudgetExceededError(
                f"Fetching page {self.meta.page + 1} is estimated at {next_cost} units; "
                f"{spent} already spent in this iteration against max_units={max_units}. "
                "Nothing more was sent.",
                estimated_cost=next_cost,
                limit=max_units,
                spent=spent,
                items_yielded=items_yielded,
            )

    def _fetcher(self) -> Any:
        if self._fetch_page is None:
            raise RuntimeError(
                "This page was not produced by a client and cannot fetch the one after it."
            )
        return self._fetch_page


class SyncPage(_PageBase[ItemT]):
    """A page returned by a synchronous client."""

    def attach_pagination(
        self, fetch_page: Callable[[int], Self], *, page_cost_estimate: int
    ) -> None:
        """Give the page a way to fetch others. Called by the resource that produced it."""
        self._fetch_page = fetch_page
        self._page_cost_estimate = page_cost_estimate

    def next_page(self) -> Self | None:
        """Fetch the page after this one, or return ``None`` on the last page. Billed."""
        if not self.has_next:
            return None
        following: Self = self._fetcher()(self.meta.page + 1)
        return following

    def iter_pages(
        self, *, max_pages: int | None = None, max_units: int | None = None
    ) -> Iterator[Self]:
        """Yield this page, then each following page as it is fetched.

        ``max_pages`` caps the pages requested beyond this one and stops
        quietly. ``max_units`` caps what the iteration may spend: a page that
        would cross it raises :class:`BudgetExceededError` before being
        requested, after everything already paid for was yielded.
        """
        yield self
        current = self
        fetched = 0
        spent = 0
        items_yielded = len(self.data)
        while current.has_next:
            if max_pages is not None and fetched >= max_pages:
                return
            current._check_budget(spent=spent, max_units=max_units, items_yielded=items_yielded)
            following = current.next_page()
            if following is None or not following.data:
                return
            fetched += 1
            spent += following.usage.query_cost if following.usage is not None else 0
            items_yielded += len(following.data)
            yield following
            current = following

    def iter_all(
        self, *, max_pages: int | None = None, max_units: int | None = None
    ) -> Iterator[ItemT]:
        """Yield every item of this page and of the following ones. Same limits as ``iter_pages``."""
        for page in self.iter_pages(max_pages=max_pages, max_units=max_units):
            yield from page.data


class AsyncPage(_PageBase[ItemT]):
    """A page returned by an asynchronous client."""

    def attach_pagination(
        self, fetch_page: Callable[[int], Awaitable[Self]], *, page_cost_estimate: int
    ) -> None:
        """Give the page a way to fetch others. Called by the resource that produced it."""
        self._fetch_page = fetch_page
        self._page_cost_estimate = page_cost_estimate

    async def next_page(self) -> Self | None:
        """Fetch the page after this one, or return ``None`` on the last page. Billed."""
        if not self.has_next:
            return None
        following: Self = await self._fetcher()(self.meta.page + 1)
        return following

    async def iter_pages(
        self, *, max_pages: int | None = None, max_units: int | None = None
    ) -> AsyncIterator[Self]:
        """Yield this page, then each following page as it is fetched. See :meth:`SyncPage.iter_pages`."""
        yield self
        current = self
        fetched = 0
        spent = 0
        items_yielded = len(self.data)
        while current.has_next:
            if max_pages is not None and fetched >= max_pages:
                return
            current._check_budget(spent=spent, max_units=max_units, items_yielded=items_yielded)
            following = await current.next_page()
            if following is None or not following.data:
                return
            fetched += 1
            spent += following.usage.query_cost if following.usage is not None else 0
            items_yielded += len(following.data)
            yield following
            current = following

    async def iter_all(
        self, *, max_pages: int | None = None, max_units: int | None = None
    ) -> AsyncIterator[ItemT]:
        """Yield every item of this page and of the following ones. Same limits as ``iter_pages``."""
        async for page in self.iter_pages(max_pages=max_pages, max_units=max_units):
            for item in page.data:
                yield item
