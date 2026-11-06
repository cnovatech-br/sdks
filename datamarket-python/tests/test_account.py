from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from conftest import load_fixture

from cnovatech.datamarket import models

if TYPE_CHECKING:
    from conftest import FakeAPI


def test_profile_is_free_and_typed(api: FakeAPI) -> None:
    expected = load_fixture("getProfile.json")
    api.respond("GET", "/api/v1/user/profile", expected)

    with api.client() as client:
        profile = client.account.profile()

    assert isinstance(profile, models.Profile)
    assert profile.email == expected["email"]
    assert profile.subscription is not None
    assert profile.subscription.plan.code == expected["subscription"]["plan"]["code"]
    assert profile.subscription.plan.limits == expected["subscription"]["plan"]["limits"]
    assert profile.trial.is_trial == expected["trial"]["is_trial"]
    assert profile.usage.remaining == expected["usage"]["remaining"]
    # Python 3.10's fromisoformat does not accept the "Z" suffix the API sends.
    assert profile.created_at == datetime.datetime.fromisoformat(
        expected["created_at"].replace("Z", "+00:00")
    )
    assert client.usage.spent == 0
    assert client.usage.calls == 0


def test_usage_history_by_day_and_month(api: FakeAPI) -> None:
    expected = load_fixture("getUsage.json")
    api.respond("GET", "/api/v1/user/usage", expected)

    with api.client() as client:
        history = client.account.usage()

    assert history.daily[0].date == datetime.date.fromisoformat(expected["daily"][0]["date"])
    assert history.monthly[0].month == expected["monthly"][0]["month"]
    assert history.to_dataframe()["used"].tolist() == [day["used"] for day in expected["daily"]]
    assert history.to_dataframe(period="monthly")["call_count"].tolist() == [
        month["call_count"] for month in expected["monthly"]
    ]


def test_logs_translate_the_filters(api: FakeAPI) -> None:
    expected = load_fixture("getUserLogs.json")
    api.respond("GET", "/api/v1/user/logs", expected)

    with api.client() as client:
        page = client.account.logs(
            status="error",
            search="stores",
            start_date=datetime.date(2026, 11, 1),
            end_date="2026-11-02",
            limit=5,
        )

    assert isinstance(page, models.LogsPage)
    assert page.summary.request_count == expected["summary"]["request_count"]
    assert page.data[0].endpoint == expected["data"][0]["endpoint"]
    assert page.data[0].query_params == expected["data"][0]["query_params"]
    assert page.usage is None
    assert page.page_cost_estimate == 0
    assert page.estimate_remaining_cost() == 0
    assert api.last_params == {
        "status_filter": "error",
        "search": "stores",
        "start_date": "2026-11-01",
        "end_date": "2026-11-02",
        "page": "1",
        "limit": "5",
    }


def test_api_keys(api: FakeAPI) -> None:
    expected = load_fixture("listApiKeys.json")
    api.respond("GET", "/api/v1/user/api-keys", expected)

    with api.client() as client:
        keys = client.account.api_keys()

    assert isinstance(keys, models.ApiKeys)
    assert [key.key_prefix for key in keys.data] == [key["key_prefix"] for key in expected["data"]]
    assert keys.data[0].expires_at is None
    assert keys.to_dataframe()["name"].tolist() == [key["name"] for key in expected["data"]]


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

    assert profile.is_verified is True
    assert len(history.monthly) >= 1
    assert isinstance(logs, models.AsyncLogsPage)
    assert len(keys.data) >= 1
    assert client.usage.spent == 0
