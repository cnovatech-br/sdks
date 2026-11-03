"""Smoke tests against the real API. Run with ``pytest --live``.

Only free endpoints are called. The health check needs no key; the account
checks need ``DATAMARKET_API_KEY`` and are skipped without it.
"""

from __future__ import annotations

import os

import pytest

from cnovatech.datamarket import DataMarket, models

pytestmark = pytest.mark.live

needs_key = pytest.mark.skipif(
    not os.environ.get("DATAMARKET_API_KEY"), reason="DATAMARKET_API_KEY is not set"
)


def test_health_endpoint_answers() -> None:
    with DataMarket() as client:
        health = client.health()

    assert health.healthy is True
    assert health.request_info is not None
    assert health.request_info.status_code == 200


@needs_key
def test_account_endpoints_answer_without_spending_quota() -> None:
    with DataMarket() as client:
        profile = client.account.profile()
        history = client.account.usage()
        logs = client.account.logs(limit=5)
        keys = client.account.api_keys()

    assert isinstance(profile, models.Profile)
    assert profile.usage.limit is None or profile.usage.remaining is not None
    assert isinstance(history, models.UsageHistory)
    assert isinstance(logs, models.LogsPage)
    assert any(key.is_active for key in keys.data)
    assert client.usage.spent == 0
    assert client.rate_limit.limit is not None
