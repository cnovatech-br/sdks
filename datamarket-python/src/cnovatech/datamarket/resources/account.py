"""Account: profile, quota history, request log and API keys. Nothing here consumes quota."""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from cnovatech.datamarket.models.account import AsyncLogsPage, LogsPage
from cnovatech.datamarket.resources import _operations as operations
from cnovatech.datamarket.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    import datetime

    from cnovatech.datamarket.models.account import ApiKeys, Profile, UsageHistory
    from cnovatech.datamarket.types import LogStatus


class Account(SyncResource):
    """Profile, quota history, request log and API keys. Free of quota cost."""

    def profile(self) -> Profile:
        """The account, its subscription, trial and the quota of the current cycle."""
        return self._execute(operations.profile())

    def usage(self) -> UsageHistory:
        """Quota consumption: the last 30 days with usage and the last 12 months."""
        return self._execute(operations.usage_history())

    def logs(
        self,
        *,
        status: LogStatus | None = None,
        search: str | None = None,
        start_date: datetime.date | str | None = None,
        end_date: datetime.date | str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> LogsPage:
        """Requests made with the account's keys, most recent first.

        Args:
            status: ``"success"`` for 2xx responses or ``"error"`` for 4xx and above.
            search: Words of the endpoint, HTTP method or IP address.
            start_date: First day of the period, as a date or ``YYYY-MM-DD``.
            end_date: Last day of the period, as a date or ``YYYY-MM-DD``.
            page: Page number, from 1.
            limit: Entries per page, up to 100.
        """
        return self._execute_paginated(
            partial(
                operations.logs,
                LogsPage,
                status=status,
                search=search,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            ),
            page=page,
        )

    def api_keys(self) -> ApiKeys:
        """The account's API keys, without their secrets, most recent first."""
        return self._execute(operations.api_keys())


class AsyncAccount(AsyncResource):
    """Profile, quota history, request log and API keys. Free of quota cost."""

    async def profile(self) -> Profile:
        """The account and the quota of the current cycle. See :meth:`Account.profile`."""
        return await self._execute(operations.profile())

    async def usage(self) -> UsageHistory:
        """Quota consumption by day and by month. See :meth:`Account.usage`."""
        return await self._execute(operations.usage_history())

    async def logs(
        self,
        *,
        status: LogStatus | None = None,
        search: str | None = None,
        start_date: datetime.date | str | None = None,
        end_date: datetime.date | str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> AsyncLogsPage:
        """Requests made with the account's keys. See :meth:`Account.logs`."""
        return await self._execute_paginated(
            partial(
                operations.logs,
                AsyncLogsPage,
                status=status,
                search=search,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            ),
            page=page,
        )

    async def api_keys(self) -> ApiKeys:
        """The account's API keys. See :meth:`Account.api_keys`."""
        return await self._execute(operations.api_keys())
