from __future__ import annotations

import pickle

import httpx
import pytest

from cnovatech.sdk_core.errors import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BudgetExceededError,
    CnovatechError,
    ConfigurationError,
    FieldError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    TrialExpiredError,
    UnexpectedResponseError,
    UnprocessableEntityError,
    error_class_for,
    error_from_response,
    parse_retry_after,
    response_error_code,
)


def quota_error() -> APIStatusError:
    return error_from_response(
        httpx.Response(
            429,
            json={
                "error": "insufficient_quota",
                "message": "Not enough units left.",
                "what_to_do": "Renew early.",
                "usage": {"query_cost": 8, "used": 995, "limit": 1000, "remaining": 5},
                "upgrade_url": "https://example.test/upgrade",
            },
            headers={"Retry-After": "1", "X-Correlation-ID": "corr-q"},
        )
    )


@pytest.mark.parametrize(
    ("status_code", "code", "expected"),
    [
        (400, "bad_request", BadRequestError),
        (401, "unauthorized", AuthenticationError),
        (402, "trial_expired", TrialExpiredError),
        (403, "forbidden", PermissionDeniedError),
        (404, "not_found", NotFoundError),
        (409, "conflict", APIStatusError),
        (422, "validation_error", UnprocessableEntityError),
        (429, "rate_limit_exceeded", RateLimitError),
        (429, "monthly_limit_exceeded", QuotaExceededError),
        (429, "trial_quota_exceeded", QuotaExceededError),
        (429, "insufficient_quota", QuotaExceededError),
        (500, "internal_server_error", ServerError),
        (502, "bad_gateway", ServerError),
        (504, "gateway_timeout", ServerError),
    ],
)
def test_error_class_by_status_and_code(
    status_code: int, code: str, expected: type[APIStatusError]
) -> None:
    assert error_class_for(status_code, code) is expected


def test_override_by_code_wins_over_status() -> None:
    class ProductNotFoundError(NotFoundError):
        pass

    overrides = {"thing_not_found": ProductNotFoundError}

    assert error_class_for(404, "thing_not_found", overrides) is ProductNotFoundError
    assert error_class_for(404, "not_found", overrides) is NotFoundError


def test_every_status_error_is_a_cnovatech_error() -> None:
    assert issubclass(APIStatusError, CnovatechError)
    assert issubclass(QuotaExceededError, APIStatusError)


def test_error_from_json_body() -> None:
    response = httpx.Response(
        404,
        json={
            "error": "thing_not_found",
            "message": "Thing 123 does not exist.",
            "what_to_do": "Search the catalogue first.",
            "timestamp": "2026-11-02T00:00:00+00:00",
        },
        headers={"X-Correlation-ID": "corr-1"},
    )

    error = error_from_response(response)

    assert isinstance(error, NotFoundError)
    assert error.status_code == 404
    assert error.code == "thing_not_found"
    assert error.message == "Thing 123 does not exist."
    assert error.hint == "Search the catalogue first."
    assert error.correlation_id == "corr-1"
    assert error.body["timestamp"] == "2026-11-02T00:00:00+00:00"
    assert str(error) == (
        "HTTP 404 thing_not_found: Thing 123 does not exist. Search the catalogue first. "
        "[correlation_id=corr-1]"
    )


def test_error_from_non_json_body_falls_back_to_status() -> None:
    response = httpx.Response(
        502, text="<html>Bad Gateway</html>", headers={"Content-Type": "text/html"}
    )

    error = error_from_response(response)

    assert isinstance(error, ServerError)
    assert error.code == "bad_gateway"
    assert error.message == "Bad Gateway"
    assert error.body == {}
    assert error.correlation_id is None
    assert str(error) == "HTTP 502 bad_gateway: Bad Gateway"


def test_rate_limit_error_reads_retry_after() -> None:
    response = httpx.Response(
        429,
        json={"error": "rate_limit_exceeded", "message": "Slow down."},
        headers={"Retry-After": "7"},
    )

    error = error_from_response(response)

    assert isinstance(error, RateLimitError)
    assert error.retry_after == 7


def test_quota_error_carries_usage_and_renewal_details() -> None:
    response = httpx.Response(
        429,
        json={
            "error": "insufficient_quota",
            "message": "Not enough units left for this call.",
            "usage": {"query_cost": 8, "used": 995, "limit": 1000, "remaining": 5},
            "can_renew": True,
            "upgrade_url": "https://example.test/upgrade",
            "early_renewal_url": "https://example.test/renew",
        },
    )

    error = error_from_response(response)

    assert isinstance(error, QuotaExceededError)
    assert error.retry_after is None
    assert error.usage is not None
    assert error.usage.remaining == 5
    assert error.can_renew is True
    assert error.upgrade_url == "https://example.test/upgrade"
    assert error.early_renewal_url == "https://example.test/renew"


def test_malformed_usage_block_is_ignored() -> None:
    response = httpx.Response(
        429, json={"error": "insufficient_quota", "usage": {"query_cost": "many"}}
    )

    assert error_from_response(response).usage is None


def test_trial_expired_details() -> None:
    response = httpx.Response(
        402,
        json={
            "error": "trial_expired",
            "message": "Your trial ended.",
            "trial_ends_at": "2026-10-01T00:00:00+00:00",
            "upgrade_url": "https://example.test/plans",
        },
    )

    error = error_from_response(response)

    assert isinstance(error, TrialExpiredError)
    assert error.trial_ends_at == "2026-10-01T00:00:00+00:00"
    assert error.upgrade_url == "https://example.test/plans"


def test_validation_error_details() -> None:
    response = httpx.Response(
        422,
        json={
            "error": "validation_error",
            "message": "The submitted data is invalid",
            "details": [
                {
                    "field": "query -> limit",
                    "message": "must be <= 1000",
                    "type": "less_than_equal",
                },
                "not a mapping",
            ],
        },
    )

    error = error_from_response(response)

    assert isinstance(error, UnprocessableEntityError)
    assert error.details == [
        FieldError(field="query -> limit", message="must be <= 1000", type="less_than_equal")
    ]


def test_validation_error_without_details() -> None:
    error = error_from_response(httpx.Response(422, json={"error": "validation_error"}))

    assert isinstance(error, UnprocessableEntityError)
    assert error.details == []


def test_non_numeric_retry_after_is_ignored() -> None:
    response = httpx.Response(
        429, json={"error": "rate_limit_exceeded"}, headers={"Retry-After": "soon"}
    )

    assert error_from_response(response).retry_after is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        ("7", 7),
        (" 12 ", 12),
        ("0", 0),
        ("-1", None),
        ("soon", None),
        ("²", None),
        ("Wed, 21 Oct 2026 07:28:00 GMT", None),
    ],
)
def test_parse_retry_after(value: str | None, expected: int | None) -> None:
    assert parse_retry_after(value) == expected


def test_correlation_id_falls_back_to_the_one_sent_when_not_echoed() -> None:
    response = httpx.Response(503, json={"error": "service_unavailable"})

    error = error_from_response(response, fallback_correlation_id="sent-by-sdk")

    assert error.correlation_id == "sent-by-sdk"


def test_echoed_correlation_id_wins_over_the_fallback() -> None:
    response = httpx.Response(503, json={}, headers={"X-Correlation-ID": "echoed"})

    assert error_from_response(response, fallback_correlation_id="sent").correlation_id == "echoed"


def test_response_error_code_defaults_by_status() -> None:
    assert response_error_code(httpx.Response(503, text="down")) == "service_unavailable"
    assert response_error_code(httpx.Response(429, json={"error": "insufficient_quota"})) == (
        "insufficient_quota"
    )


def test_json_body_that_is_not_an_object_is_ignored() -> None:
    error = error_from_response(httpx.Response(400, json=["unexpected"]))

    assert isinstance(error, BadRequestError)
    assert error.body == {}
    assert error.code == "bad_request"


def test_connection_errors_show_their_correlation_id() -> None:
    error = APIConnectionError("Could not reach the API.", retryable=True, correlation_id="corr-7")

    assert str(error) == "Could not reach the API. [correlation_id=corr-7]"
    assert error.args == ("Could not reach the API.",)
    assert str(APITimeoutError("Too slow.")) == "Too slow."


@pytest.mark.parametrize(
    "error",
    [
        ConfigurationError("No key."),
        BudgetExceededError("Over.", estimated_cost=8, limit=4, spent=2, items_yielded=10),
        APIConnectionError("Down.", retryable=True, correlation_id="corr-1"),
        APITimeoutError("Slow.", correlation_id="corr-2"),
        UnexpectedResponseError(
            "HTML.", status_code=200, content_type="text/html", correlation_id="corr-3"
        ),
        quota_error(),
    ],
    ids=lambda error: type(error).__name__,
)
def test_errors_survive_pickling(error: CnovatechError) -> None:
    """Process pools and error reporters rebuild exceptions through ``pickle``."""
    restored = pickle.loads(pickle.dumps(error))  # noqa: S301 - our own bytes

    assert type(restored) is type(error)
    assert str(restored) == str(error)
    assert vars(restored) == vars(error)
