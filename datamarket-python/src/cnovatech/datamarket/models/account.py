"""Models of the account resource: profile, quota history, request log and API keys."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, ClassVar, Literal

from pydantic import Field

from cnovatech.sdk_core.dataframe import build_dataframe
from cnovatech.sdk_core.pagination import AsyncPage, SyncPage

from .common import APIResponse, Record, TabularResponse

if TYPE_CHECKING:
    import pandas

__all__ = [
    "AccountUsage",
    "ApiKey",
    "ApiKeys",
    "AsyncLogsPage",
    "LogEntry",
    "LogsPage",
    "LogsSummary",
    "Plan",
    "Profile",
    "Subscription",
    "Trial",
    "UsageDay",
    "UsageHistory",
    "UsageMonth",
]


class Plan(Record):
    """The subscribed plan."""

    code: str
    name: str
    features: dict[str, Any] = Field(default_factory=dict)
    limits: dict[str, Any] = Field(default_factory=dict)


class Subscription(Record):
    """The active subscription."""

    status: str
    plan: Plan
    billing_cycle: str | None = None
    current_period_end: datetime.datetime | None = None
    cancel_at_period_end: bool = False


class Trial(Record):
    """Situation of the free trial."""

    is_trial: bool
    started_at: datetime.datetime | None = None
    ends_at: datetime.datetime | None = None
    days_remaining: int = 0
    expired: bool = False


class AccountUsage(Record):
    """Consumption of the current cycle, as shown in the profile.

    ``used``, ``limit`` and ``remaining`` are ``None`` on plans without a ceiling.
    """

    used: int | None = None
    limit: int | None = None
    remaining: int | None = None
    plan_limit: int | None = None
    bonus: int = 0
    can_early_renew: bool = False
    early_renewal_count: int = 0
    early_renewal_max: int = 3


class Profile(APIResponse):
    """The account: identity, subscription, trial and quota of the current cycle."""

    id: str
    email: str
    name: str
    profile: str
    company_name: str | None = None
    company_document: str | None = None
    phone: str | None = None
    is_verified: bool
    created_at: datetime.datetime
    last_login_at: datetime.datetime | None = None
    subscription: Subscription | None = None
    trial: Trial
    usage: AccountUsage


class UsageDay(Record):
    """Consumption of one day."""

    date: datetime.date
    used: int
    call_count: int


class UsageMonth(Record):
    """Consumption of one calendar month."""

    month: str
    used: int
    call_count: int


class UsageHistory(TabularResponse):
    """Consumption history: the last 30 days with usage and the last 12 months."""

    rows_field: ClassVar[str] = "daily"

    daily: list[UsageDay] = Field(default_factory=list)
    monthly: list[UsageMonth] = Field(default_factory=list)

    def to_dataframe(
        self,
        *,
        include_envelope: bool = True,
        period: Literal["daily", "monthly"] = "daily",
    ) -> pandas.DataFrame:
        """One row per day, or per month with ``period="monthly"``.

        Requires pandas, available through the SDK's ``pandas`` extra.
        """
        return build_dataframe(self, rows_field=period, include_envelope=include_envelope)


class LogEntry(Record):
    """One request recorded in the account's log."""

    id: int
    endpoint: str
    method: str
    status_code: int
    response_time_ms: int
    ip_address: str | None = None
    created_at: datetime.datetime
    query_params: dict[str, Any] | None = None
    api_key_prefix: str | None = None


class LogsSummary(Record):
    """Totals of the whole filtered period, not only the page."""

    request_count: int
    success_pct: int
    median_response_time_ms: int
    error_count: int


class LogsEnvelope(APIResponse):
    """Envelope of the request log."""

    summary: LogsSummary


class LogsPage(SyncPage[LogEntry], LogsEnvelope):
    """One page of the request log. Free of quota cost."""


class AsyncLogsPage(AsyncPage[LogEntry], LogsEnvelope):
    """One page of the request log, from the asynchronous client."""


class ApiKey(Record):
    """An API key of the account, without the secret."""

    id: str
    key_prefix: str
    name: str | None = None
    is_active: bool
    last_used_at: datetime.datetime | None = None
    expires_at: datetime.datetime | None = None
    created_at: datetime.datetime


class ApiKeys(TabularResponse):
    """The API keys of the account, from the most recent to the oldest."""

    data: list[ApiKey] = Field(default_factory=list)
