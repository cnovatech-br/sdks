"""Exception hierarchy shared by the Cnovatech SDKs.

Every exception raised on purpose by an SDK derives from :class:`CnovatechError`,
so a single ``except CnovatechError`` clause catches anything the SDK produces.
Errors reported by the API become :class:`APIStatusError` subclasses, chosen by
HTTP status and, for 429 responses, by the ``error`` code in the body.

Messages never include the API key or the request URL with its query string.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pydantic

from .models import Usage

if TYPE_CHECKING:
    import httpx

CORRELATION_ID_HEADER = "X-Correlation-ID"
RETRY_AFTER_HEADER = "Retry-After"
RATE_LIMIT_CODE = "rate_limit_exceeded"

# Codes the API assigns when an error body does not name its own.
_DEFAULT_CODES: Mapping[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    422: "validation_error",
    429: "rate_limit_exceeded",
    500: "internal_server_error",
    502: "bad_gateway",
    503: "service_unavailable",
    504: "gateway_timeout",
}


class CnovatechError(Exception):
    """Base class of every error raised by a Cnovatech SDK."""


class ConfigurationError(CnovatechError, ValueError):
    """The client was configured with a missing or invalid value. Nothing was sent."""


class BudgetExceededError(CnovatechError):
    """A call or an iteration would cost more quota than the configured ceiling.

    Raised before the request is sent, so nothing was billed.

    Attributes:
        estimated_cost: Units the refused request was expected to consume.
        limit: The ceiling that would have been crossed.
        spent: Units already consumed by the iteration that stopped, if any.
        items_yielded: Items delivered before the iteration stopped, if any.
    """

    def __init__(
        self,
        message: str,
        *,
        estimated_cost: int,
        limit: int,
        spent: int = 0,
        items_yielded: int = 0,
    ) -> None:
        super().__init__(message)
        self.estimated_cost = estimated_cost
        self.limit = limit
        self.spent = spent
        self.items_yielded = items_yielded


class APIConnectionError(CnovatechError):
    """No usable response was received: DNS, TCP, TLS or a similar transport failure.

    Attributes:
        retryable: Whether the request can be repeated without risk of a second
            charge, which is the case only when it never reached the API. The
            SDK retries on its own only when this is true.
    """

    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable


class APITimeoutError(APIConnectionError):
    """The API did not answer within the read timeout.

    Never retried by the SDK: the server may already have processed and billed
    the request, and a repeat could be charged again.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message, retryable=False)


class UnexpectedResponseError(CnovatechError):
    """The response was not the JSON document the SDK expected.

    Attributes:
        status_code: HTTP status of the response.
        content_type: Value of the ``Content-Type`` header, if any.
        correlation_id: Identifier of the request, for support.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        content_type: str | None,
        correlation_id: str | None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.content_type = content_type
        self.correlation_id = correlation_id


@dataclass(frozen=True, slots=True)
class FieldError:
    """One invalid field reported by a 422 response."""

    field: str
    message: str
    type: str


class APIStatusError(CnovatechError):
    """The API answered with an error status.

    Attributes:
        status_code: HTTP status of the response.
        code: Machine-readable error code from the body, or a default derived
            from the status when the body does not carry one.
        message: Human-readable message from the body.
        body: Decoded JSON body, or an empty mapping when the body was not JSON.
        correlation_id: Identifier of the request. Quote it in support requests.
        hint: What the API suggests doing next, when it says.
        usage: Quota accounting sent with the error, when present.
        retry_after: Seconds to wait before trying again, from ``Retry-After``.
    """

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        body: Mapping[str, Any] | None = None,
        correlation_id: str | None = None,
        hint: str | None = None,
        usage: Usage | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.body: Mapping[str, Any] = body if body is not None else {}
        self.correlation_id = correlation_id
        self.hint = hint
        self.usage = usage
        self.retry_after = retry_after

    def __str__(self) -> str:
        text = f"HTTP {self.status_code} {self.code}: {self.message}"
        if self.hint:
            text = f"{text} {self.hint}"
        if self.correlation_id:
            text = f"{text} [correlation_id={self.correlation_id}]"
        return text

    def _body_text(self, key: str) -> str | None:
        value = self.body.get(key)
        return value if isinstance(value, str) else None


class BadRequestError(APIStatusError):
    """400: the request was understood but refused."""


class AuthenticationError(APIStatusError):
    """401: the API key is missing, invalid or revoked."""


class TrialExpiredError(APIStatusError):
    """402: the trial period ended and no subscription is active."""

    @property
    def trial_ends_at(self) -> str | None:
        """When the trial ended, as reported by the API."""
        return self._body_text("trial_ends_at")

    @property
    def upgrade_url(self) -> str | None:
        """Where to subscribe, as reported by the API."""
        return self._body_text("upgrade_url")


class PermissionDeniedError(APIStatusError):
    """403: the key is valid but not allowed to perform this call."""


class NotFoundError(APIStatusError):
    """404: the requested entity does not exist."""


class UnprocessableEntityError(APIStatusError):
    """422: the request did not pass the API's validation."""

    @property
    def details(self) -> list[FieldError]:
        """The invalid fields, one entry each."""
        raw_details = self.body.get("details")
        if not isinstance(raw_details, list):
            return []
        return [
            FieldError(
                field=str(item.get("field", "")),
                message=str(item.get("message", "")),
                type=str(item.get("type", "")),
            )
            for item in raw_details
            if isinstance(item, Mapping)
        ]


class RateLimitError(APIStatusError):
    """429 ``rate_limit_exceeded``: too many requests in the current minute.

    Safe to repeat after :attr:`retry_after` seconds. The SDK retries it on
    its own up to ``max_retries`` times before raising.
    """


class QuotaExceededError(APIStatusError):
    """429 for the monthly or trial quota. Retrying will not help.

    The ``code`` says which ceiling was hit: ``monthly_limit_exceeded``,
    ``trial_quota_exceeded`` or ``insufficient_quota``.
    """

    @property
    def can_renew(self) -> bool | None:
        """Whether an early renewal is available, as reported by the API."""
        value = self.body.get("can_renew")
        return value if isinstance(value, bool) else None

    @property
    def upgrade_url(self) -> str | None:
        """Where to change plan, as reported by the API."""
        return self._body_text("upgrade_url")

    @property
    def early_renewal_url(self) -> str | None:
        """Where to renew the quota early, as reported by the API."""
        return self._body_text("early_renewal_url")


class ServerError(APIStatusError):
    """5xx: the API or its gateway failed."""


_STATUS_TO_ERROR: Mapping[int, type[APIStatusError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    402: TrialExpiredError,
    403: PermissionDeniedError,
    404: NotFoundError,
    422: UnprocessableEntityError,
}


def error_class_for(
    status_code: int,
    code: str,
    overrides: Mapping[str, type[APIStatusError]] | None = None,
) -> type[APIStatusError]:
    """Choose the exception class for a status and error code.

    ``overrides`` maps error codes to product-specific classes and wins over
    the generic choice by status.
    """
    if overrides and code in overrides:
        return overrides[code]
    if status_code == 429:
        return RateLimitError if code == RATE_LIMIT_CODE else QuotaExceededError
    if status_code >= 500:
        return ServerError
    return _STATUS_TO_ERROR.get(status_code, APIStatusError)


def response_error_code(response: httpx.Response) -> str:
    """The ``error`` code of an error response, or the default for its status."""
    body = _json_object(response)
    return _text(body.get("error")) or _DEFAULT_CODES.get(response.status_code, "error")


def error_from_response(
    response: httpx.Response,
    *,
    overrides: Mapping[str, type[APIStatusError]] | None = None,
    fallback_correlation_id: str | None = None,
) -> APIStatusError:
    """Build the exception that describes an error response.

    Tolerates bodies that are not JSON, such as HTML from a gateway, by falling
    back to the status code and reason phrase. ``fallback_correlation_id`` is
    the identifier the SDK sent, used when the response does not echo one.
    """
    body = _json_object(response)
    status_code = response.status_code
    code = _text(body.get("error")) or _DEFAULT_CODES.get(status_code, "error")
    message = _text(body.get("message")) or response.reason_phrase or f"HTTP {status_code}"
    error_class = error_class_for(status_code, code, overrides)
    return error_class(
        status_code=status_code,
        code=code,
        message=message,
        body=body,
        correlation_id=response.headers.get(CORRELATION_ID_HEADER) or fallback_correlation_id,
        hint=_text(body.get("what_to_do")),
        usage=_usage(body.get("usage")),
        retry_after=parse_retry_after(response.headers.get(RETRY_AFTER_HEADER)),
    )


def parse_retry_after(value: str | None) -> int | None:
    """Seconds from a ``Retry-After`` header, or ``None`` when absent or not a delay in seconds."""
    if value is None:
        return None
    try:
        seconds = int(value.strip())
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


def _json_object(response: httpx.Response) -> Mapping[str, Any]:
    try:
        decoded = response.json()
    except ValueError:
        return {}
    return decoded if isinstance(decoded, Mapping) else {}


def _text(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _usage(value: object) -> Usage | None:
    if not isinstance(value, Mapping):
        return None
    try:
        return Usage.model_validate(value)
    except pydantic.ValidationError:
        return None
