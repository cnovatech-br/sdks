"""Operation builders: validation happens before anything else, and dates keep the API's format."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from cnovatech.datamarket import errors
from cnovatech.datamarket.models.account import LogsPage
from cnovatech.datamarket.models.stores import AssortmentPage
from cnovatech.datamarket.resources import _operations as operations
from cnovatech.sdk_core import pricing

if TYPE_CHECKING:
    from conftest import FakeAPI

STORE_ID = "962a5321-d7b6-48fc-b1a5-447c7d153367"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("2026-11-01", "2026-11-01"),
        (datetime.date(2026, 11, 1), "2026-11-01"),
        (datetime.datetime(2026, 11, 1, 15, 30, tzinfo=datetime.timezone.utc), "2026-11-01"),
    ],
)
def test_log_dates_are_sent_as_calendar_days(
    value: datetime.date | str | None, expected: str | None
) -> None:
    operation = operations.logs(
        LogsPage, status=None, search=None, start_date=value, end_date=None, limit=20, page=1
    )

    assert operation.params["start_date"] == expected


def test_page_cost_follows_the_validated_limit() -> None:
    operation = operations.assortment(AssortmentPage, store_id=STORE_ID, limit=1000, page=1)

    assert operation.estimated_cost == pricing.export_cost(1000) == 8


def test_an_invalid_limit_is_an_sdk_error_even_for_paginated_calls(api: FakeAPI) -> None:
    with api.client() as client, pytest.raises(errors.InvalidRequestError, match="limit"):
        client.stores.assortment(STORE_ID, limit="100")  # type: ignore[arg-type]

    assert api.requests == []
