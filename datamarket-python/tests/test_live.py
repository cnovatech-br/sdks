"""Smoke tests against the real API. Run with ``pytest --live``. Only free endpoints."""

from __future__ import annotations

import pytest

from cnovatech.datamarket import DataMarket

pytestmark = pytest.mark.live


def test_health_endpoint_answers() -> None:
    with DataMarket() as client:
        health = client.health()

    assert health.healthy is True
    assert health.request_info is not None
    assert health.request_info.status_code == 200
