from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from cnovatech.sdk_core.models import APIResponse, Usage, parser_for
from cnovatech.sdk_core.operation import Operation
from cnovatech.sdk_core.usage import RateLimitState, UsageTracker, record_usage

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest

    from cnovatech.sdk_core.transport import SyncTransport


class Billed(APIResponse):
    name: str
    usage: Usage


class Free(APIResponse):
    name: str


def usage(cost: int, *, remaining: int | None = 500, limit: int | None = 1000) -> Usage:
    return Usage(query_cost=cost, used=None, limit=limit, remaining=remaining)


def test_tracker_accumulates_cost_and_keeps_the_last_block() -> None:
    tracker = UsageTracker()

    tracker.record(usage(1, remaining=999))
    tracker.record(usage(8, remaining=991))

    assert tracker.spent == 9
    assert tracker.calls == 2
    assert tracker.last is not None
    assert tracker.last.remaining == 991
    assert repr(tracker) == "UsageTracker(spent=9, calls=2, remaining=991)"


def test_tracker_starts_empty() -> None:
    assert repr(UsageTracker()) == "UsageTracker(spent=0, calls=0, remaining=None)"


def test_low_quota_is_warned_once_per_crossing(caplog: pytest.LogCaptureFixture) -> None:
    tracker = UsageTracker()

    with caplog.at_level(logging.WARNING, logger="cnovatech"):
        tracker.record(usage(1, remaining=150))
        tracker.record(usage(1, remaining=99))
        tracker.record(usage(1, remaining=50))
        tracker.record(usage(1, remaining=900))
        tracker.record(usage(1, remaining=20))

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert [record.getMessage() for record in warnings] == [
        "Quota is running low: 99 of 1000 units remaining in this cycle",
        "Quota is running low: 20 of 1000 units remaining in this cycle",
    ]
    assert warnings[0].remaining == 99  # type: ignore[attr-defined]


def test_unlimited_plans_never_warn(caplog: pytest.LogCaptureFixture) -> None:
    tracker = UsageTracker()

    with caplog.at_level(logging.WARNING, logger="cnovatech"):
        tracker.record(usage(1, remaining=None, limit=None))
        tracker.record(usage(1, remaining=0, limit=0))

    assert caplog.records == []


def test_record_usage_reads_the_usage_block_when_present() -> None:
    tracker = UsageTracker()

    record_usage(tracker, Billed(name="a", usage=usage(3)))
    record_usage(tracker, Free(name="b"))
    record_usage(tracker, "not a model")

    assert tracker.spent == 3
    assert tracker.calls == 1


def test_rate_limit_state_reads_headers() -> None:
    state = RateLimitState()

    state.update_from_headers(
        httpx.Headers(
            {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "42", "X-RateLimit-Reset": "17"}
        )
    )

    assert state.limit == 60
    assert state.remaining == 42
    assert state.reset_in_seconds == 17
    assert state.observed_at is not None


def test_rate_limit_state_ignores_responses_without_headers() -> None:
    state = RateLimitState()
    state.update_from_headers(
        httpx.Headers({"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "5"})
    )

    state.update_from_headers(httpx.Headers({"Content-Type": "application/json"}))

    assert state.remaining == 5


def test_rate_limit_state_tolerates_malformed_values() -> None:
    state = RateLimitState()

    state.update_from_headers(
        httpx.Headers({"X-RateLimit-Limit": "sixty", "X-RateLimit-Remaining": "5"})
    )

    assert state.limit is None
    assert state.remaining == 5
    assert state.reset_in_seconds is None


def test_transport_feeds_usage_and_rate_limit(
    make_sync_transport: Callable[..., SyncTransport],
    json_response: Callable[..., Any],
) -> None:
    handler = json_response(
        200,
        {"name": "a", "usage": {"query_cost": 2, "used": 10, "limit": 100, "remaining": 90}},
        headers={
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "59",
            "X-RateLimit-Reset": "30",
        },
    )
    transport = make_sync_transport(handler)
    operation: Operation[Billed] = Operation(method="GET", path="/billed", parse=parser_for(Billed))

    transport.execute(operation)
    transport.execute(operation)

    assert transport.usage.spent == 4
    assert transport.usage.last is not None
    assert transport.usage.last.remaining == 90
    assert transport.rate_limit.remaining == 59
    assert transport.rate_limit.reset_in_seconds == 30


def test_two_transports_do_not_share_accounting(
    make_sync_transport: Callable[..., SyncTransport],
    json_response: Callable[..., Any],
) -> None:
    handler = json_response(200, {"name": "a", "usage": {"query_cost": 5}})
    first = make_sync_transport(handler)
    second = make_sync_transport(handler)
    operation: Operation[Billed] = Operation(method="GET", path="/billed", parse=parser_for(Billed))

    first.execute(operation)

    assert first.usage.spent == 5
    assert second.usage.spent == 0
