from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from cnovatech.datamarket import models

if TYPE_CHECKING:
    from conftest import FakeAPI


def test_profile_is_free_and_typed(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/user/profile", "getProfile.json")

    with api.client() as client:
        profile = client.account.profile()

    assert isinstance(profile, models.Profile)
    assert profile.subscription is not None
    assert profile.subscription.plan.code == "pro"
    assert profile.subscription.plan.limits["requests_per_minute"] == 60
    assert profile.trial.expired is True
    assert profile.usage.remaining == 974
    assert profile.created_at == datetime.datetime(
        2026, 9, 15, 13, 20, tzinfo=datetime.timezone.utc
    )
    assert client.usage.spent == 0
    assert client.usage.calls == 0


def test_usage_history_by_day_and_month(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/user/usage", "getUsage.json")

    with api.client() as client:
        history = client.account.usage()

    assert history.daily[0].date == datetime.date(2026, 11, 2)
    assert history.monthly[1].month == "2026-10"
    assert history.to_dataframe()["used"].tolist() == [26, 12]
    assert history.to_dataframe(period="monthly")["call_count"].tolist() == [28, 190]


def test_logs_translate_the_filters(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/user/logs", "getUserLogs.json")

    with api.client() as client:
        page = client.account.logs(
            status="error",
            search="ean",
            start_date=datetime.date(2026, 11, 1),
            end_date="2026-11-02",
            limit=100,
        )

    assert isinstance(page, models.LogsPage)
    assert page.summary.request_count == 19
    assert page.data[1].status_code == 404
    assert page.data[0].query_params == {"state": "SP"}
    assert page.usage is None
    assert page.page_cost_estimate == 0
    assert api.last_params == {
        "status_filter": "error",
        "search": "ean",
        "start_date": "2026-11-01",
        "end_date": "2026-11-02",
        "page": "1",
        "limit": "100",
    }


def test_api_keys(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/user/api-keys", "listApiKeys.json")

    with api.client() as client:
        keys = client.account.api_keys()

    assert isinstance(keys, models.ApiKeys)
    assert keys.data[0].key_prefix == "dm_12ab"
    assert keys.data[0].expires_at is None
    assert keys.to_dataframe()["name"].tolist() == ["Pipeline"]


async def test_async_account(api: FakeAPI) -> None:
    api.respond("GET", "/api/v1/user/profile", "getProfile.json")
    api.respond("GET", "/api/v1/user/usage", "getUsage.json")
    api.respond("GET", "/api/v1/user/logs", "getUserLogs.json")
    api.respond("GET", "/api/v1/user/api-keys", "listApiKeys.json")

    async with api.async_client() as client:
        profile = await client.account.profile()
        history = await client.account.usage()
        logs = await client.account.logs()
        keys = await client.account.api_keys()

    assert profile.email == "analyst@example.test"
    assert len(history.monthly) == 2
    assert isinstance(logs, models.AsyncLogsPage)
    assert len(keys.data) == 1
