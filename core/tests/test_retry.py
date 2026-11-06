from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import httpx
import pytest
from conftest import json_response, ok, predictable_policy, sequence, thing_operation

from cnovatech.sdk_core.errors import (
    APIConnectionError,
    APITimeoutError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
)
from cnovatech.sdk_core.retry import BACKOFF_MAX_SECONDS, RETRY_AFTER_MAX_SECONDS, RetryPolicy

if TYPE_CHECKING:
    from collections.abc import Callable

    from cnovatech.sdk_core.transport import AsyncTransport, SyncTransport


def rate_limited(retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(429, json={"error": "rate_limit_exceeded"}, headers=headers)


# --- policy -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("attempt", "expected"),
    [(1, 0.5), (2, 1.0), (3, 2.0), (4, 4.0), (5, 8.0), (6, BACKOFF_MAX_SECONDS)],
)
def test_backoff_doubles_up_to_the_cap(attempt: int, expected: float) -> None:
    assert predictable_policy(10).backoff(attempt) == expected


def test_backoff_jitter_keeps_between_half_and_all_of_the_nominal_delay() -> None:
    assert RetryPolicy(1, random_fraction=lambda: 0.0).backoff(1) == 0.25
    assert RetryPolicy(1, random_fraction=lambda: 0.5).backoff(1) == 0.375


@pytest.mark.parametrize("status_code", [502, 503])
def test_gateway_errors_are_repeated(status_code: int) -> None:
    decision = predictable_policy(2).after_response(httpx.Response(status_code), attempt=1)

    assert decision is not None
    assert decision.reason == f"HTTP {status_code}"
    assert decision.delay_seconds == 0.5


def test_gateway_errors_wait_for_retry_after_when_given() -> None:
    response = httpx.Response(503, headers={"Retry-After": "2"})

    decision = predictable_policy(2).after_response(response, attempt=1)

    assert decision is not None
    assert decision.delay_seconds == 2.0


@pytest.mark.parametrize("status_code", [400, 401, 404, 422, 500, 504])
def test_other_statuses_are_not_repeated(status_code: int) -> None:
    # 504 included: the gateway gave up, but the application may still be billing the request.
    assert RetryPolicy(2).after_response(httpx.Response(status_code), attempt=1) is None


def test_per_minute_limit_waits_for_retry_after() -> None:
    decision = RetryPolicy(2).after_response(rate_limited("7"), attempt=1)

    assert decision is not None
    assert decision.delay_seconds == 7.0
    assert decision.reason == "HTTP 429 rate_limit_exceeded"


def test_retry_after_is_capped() -> None:
    decision = RetryPolicy(2).after_response(rate_limited("3600"), attempt=1)

    assert decision is not None
    assert decision.delay_seconds == RETRY_AFTER_MAX_SECONDS


def test_per_minute_limit_without_retry_after_uses_backoff() -> None:
    decision = predictable_policy(2).after_response(rate_limited(), attempt=2)

    assert decision is not None
    assert decision.delay_seconds == 1.0


def test_quota_errors_are_not_repeated() -> None:
    response = httpx.Response(
        429, json={"error": "insufficient_quota"}, headers={"Retry-After": "1"}
    )

    assert RetryPolicy(5).after_response(response, attempt=1) is None


def test_attempts_stop_at_max_retries() -> None:
    policy = RetryPolicy(2)

    assert policy.max_attempts == 3
    assert policy.after_response(httpx.Response(503), attempt=2) is not None
    assert policy.after_response(httpx.Response(503), attempt=3) is None


def test_zero_retries_never_repeats() -> None:
    assert RetryPolicy(0).after_response(httpx.Response(503), attempt=1) is None


def test_retryable_connection_errors_are_repeated_with_the_cause_as_reason() -> None:
    error = APIConnectionError("unreachable", retryable=True)
    error.__cause__ = httpx.ConnectError("boom")

    decision = predictable_policy(1).after_exception(error, attempt=1)

    assert decision is not None
    assert decision.reason == "ConnectError"
    assert decision.delay_seconds == 0.5


def test_non_retryable_connection_errors_are_not_repeated() -> None:
    policy = RetryPolicy(5)

    assert policy.after_exception(APIConnectionError("dropped", retryable=False), attempt=1) is None
    assert policy.after_exception(APITimeoutError("slow"), attempt=1) is None


# --- transports -------------------------------------------------------------


def test_transport_recovers_from_a_gateway_error(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
    sleeps: list[float],
) -> None:
    transport = make_sync_transport(sequence(httpx.Response(503), ok()))

    thing = transport.execute(thing_operation())

    assert thing.name == "Milk"
    assert thing.request_info is not None
    assert thing.request_info.attempts == 2
    assert sleeps == [0.5]
    assert len(sent_requests) == 2


def test_every_attempt_carries_the_same_correlation_id(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    make_sync_transport(sequence(httpx.Response(502), httpx.Response(502), ok())).execute(
        thing_operation()
    )

    correlation_ids = {request.headers["X-Correlation-ID"] for request in sent_requests}
    assert len(sent_requests) == 3
    assert len(correlation_ids) == 1


def test_transport_recovers_from_a_connection_error(
    make_sync_transport: Callable[..., SyncTransport],
    sleeps: list[float],
) -> None:
    transport = make_sync_transport(sequence(httpx.ConnectError("boom"), ok()))

    thing = transport.execute(thing_operation())

    assert thing.request_info is not None
    assert thing.request_info.attempts == 2
    assert sleeps == [0.5]


def test_transport_gives_up_after_max_retries(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
    sleeps: list[float],
) -> None:
    transport = make_sync_transport(json_response(503, {"error": "service_unavailable"}))

    with pytest.raises(ServerError) as excinfo:
        transport.execute(thing_operation())

    assert excinfo.value.status_code == 503
    assert len(sent_requests) == 3
    assert sleeps == [0.5, 1.0]


def test_transport_honours_retry_after_then_raises_rate_limit_error(
    make_sync_transport: Callable[..., SyncTransport],
    sleeps: list[float],
) -> None:
    transport = make_sync_transport(
        sequence(rate_limited("3"), rate_limited("4"), rate_limited("5")), max_retries=2
    )

    with pytest.raises(RateLimitError) as excinfo:
        transport.execute(thing_operation())

    assert excinfo.value.retry_after == 5
    assert sleeps == [3.0, 4.0]


def test_transport_does_not_repeat_quota_errors(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
    sleeps: list[float],
) -> None:
    transport = make_sync_transport(json_response(429, {"error": "monthly_limit_exceeded"}))

    with pytest.raises(QuotaExceededError):
        transport.execute(thing_operation())

    assert len(sent_requests) == 1
    assert sleeps == []


def test_transport_does_not_repeat_read_timeouts(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    transport = make_sync_transport(sequence(httpx.ReadTimeout("slow"), ok()))

    with pytest.raises(APITimeoutError):
        transport.execute(thing_operation())

    assert len(sent_requests) == 1


def test_transport_with_zero_retries_sends_once(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    transport = make_sync_transport(json_response(503, {}), max_retries=0)

    with pytest.raises(ServerError):
        transport.execute(thing_operation())

    assert len(sent_requests) == 1


def test_retries_are_logged_with_structured_fields(
    make_sync_transport: Callable[..., SyncTransport],
    caplog: pytest.LogCaptureFixture,
) -> None:
    transport = make_sync_transport(sequence(httpx.Response(503), ok()))

    with caplog.at_level(logging.INFO, logger="cnovatech"):
        transport.execute(thing_operation())

    (record,) = [entry for entry in caplog.records if entry.levelno == logging.INFO]
    assert record.getMessage() == (
        "Retrying GET /api/v1/things/1 after HTTP 503: attempt 2 of 3 in 0.50s"
    )
    assert record.attempt == 2  # type: ignore[attr-defined]
    assert record.reason == "HTTP 503"  # type: ignore[attr-defined]
    assert record.path == "/api/v1/things/1"  # type: ignore[attr-defined]
    assert "ex_test_key" not in caplog.text


async def test_async_transport_recovers_from_a_gateway_error(
    make_async_transport: Callable[..., AsyncTransport],
    sleeps: list[float],
) -> None:
    async with make_async_transport(sequence(httpx.Response(503), ok())) as transport:
        thing = await transport.execute(thing_operation())

    assert thing.request_info is not None
    assert thing.request_info.attempts == 2
    assert sleeps == [0.5]


async def test_async_transport_gives_up_after_max_retries(
    make_async_transport: Callable[..., AsyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    outcomes = [httpx.ConnectError("boom")] * 3
    async with make_async_transport(sequence(*outcomes)) as transport:
        with pytest.raises(APIConnectionError):
            await transport.execute(thing_operation())

    assert len(sent_requests) == 3


async def test_async_transport_honours_retry_after_on_the_per_minute_limit(
    make_async_transport: Callable[..., AsyncTransport],
    sleeps: list[float],
) -> None:
    async with make_async_transport(sequence(rate_limited("3"), ok())) as transport:
        thing = await transport.execute(thing_operation())

    assert thing.request_info is not None
    assert thing.request_info.attempts == 2
    assert sleeps == [3.0]


async def test_async_transport_does_not_repeat_quota_errors(
    make_async_transport: Callable[..., AsyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    handler = json_response(429, {"error": "monthly_limit_exceeded"})
    async with make_async_transport(handler) as transport:
        with pytest.raises(QuotaExceededError):
            await transport.execute(thing_operation())

    assert len(sent_requests) == 1
