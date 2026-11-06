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

    def __getstate__(self) -> dict[Any, Any]:
        """Pickle the page without the fetch callback, which belongs to the client that made it.

        A page restored from a pickle keeps its data, metadata and usage, and
        can no longer fetch the pages after it.
        """
        state = super().__getstate__()
        private = state.get("__pydantic_private__")
        if private:
            state["__pydantic_private__"] = {**private, "_fetch_page": None}
        return state

    def _fetcher(self) -> Any:
        if self._fetch_page is None:
            raise RuntimeError(
                "This page was not produced by a client, or was restored from a pickle, and "
                "cannot fetch the one after it. Request the page again through the client."
            )
        return self._fetch_page


class _PageWalk:
    """Bookkeeping of one walk over consecutive pages: pages fetched, units spent, items yielded.

    Shared by the synchronous and asynchronous iterators, which differ only in
    how they wait for the next page.
    """

    def __init__(
        self, first: _PageBase[Any], *, max_pages: int | None, max_units: int | None
    ) -> None:
        self._max_pages = max_pages
        self._max_units = max_units
        self.fetched = 0
        self.spent = 0
        self.items_yielded = len(first.data)

    def may_fetch(self) -> bool:
        """Whether another page may be requested under ``max_pages``."""
        return self._max_pages is None or self.fetched < self._max_pages

    def check_budget(self, current: _PageBase[Any]) -> None:
        """Refuse, before sending, the page after ``current`` if it would cross ``max_units``."""
        next_cost = current.page_cost_estimate
        if self._max_units is not None and self.spent + next_cost > self._max_units:
            raise BudgetExceededError(
                f"Fetching page {current.meta.page + 1} is estimated at {next_cost} units; "
                f"{self.spent} already spent in this iteration against max_units={self._max_units}. "
                "Nothing more was sent.",
                estimated_cost=next_cost,
                limit=self._max_units,
                spent=self.spent,
                items_yielded=self.items_yielded,
            )

    def accept(self, following: _PageBase[Any]) -> bool:
        """Record a fetched page. ``False`` when it is empty, which ends the walk."""
        if not following.data:
            return False
        self.fetched += 1
        self.spent += following.usage.query_cost if following.usage is not None else 0
        self.items_yielded += len(following.data)
        return True


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
        walk = _PageWalk(self, max_pages=max_pages, max_units=max_units)
        yield self
        current = self
        while current.has_next and walk.may_fetch():
            walk.check_budget(current)
            following = current.next_page()
            if following is None or not walk.accept(following):
                return
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
        walk = _PageWalk(self, max_pages=max_pages, max_units=max_units)
        yield self
        current = self
        while current.has_next and walk.may_fetch():
            walk.check_budget(current)
            following = await current.next_page()
            if following is None or not walk.accept(following):
                return
            yield following
            current = following

    async def iter_all(
        self, *, max_pages: int | None = None, max_units: int | None = None
    ) -> AsyncIterator[ItemT]:
        """Yield every item of this page and of the following ones. Same limits as ``iter_pages``."""
        async for page in self.iter_pages(max_pages=max_pages, max_units=max_units):
            for item in page.data:
                yield item
