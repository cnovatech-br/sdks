"""Retry policy: which failures are repeated, and how long to wait first.

A request is repeated only when it cannot have been processed by the API, so
a retry can never bill the customer twice. The policy is pure: transports ask
it for a decision after each attempt and do the waiting themselves.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .errors import RATE_LIMIT_CODE, RETRY_AFTER_HEADER, parse_retry_after, response_error_code

if TYPE_CHECKING:
    from collections.abc import Callable

    import httpx

    from .errors import APIConnectionError

# Gateway failures that happen before the application answers, so nothing was
# billed. 504 is left out on purpose: a gateway that gives up on a slow request
# reports it while the application may still be processing and billing it.
RETRYABLE_STATUS_CODES = frozenset({502, 503})
PER_MINUTE_LIMIT_STATUS = 429

BACKOFF_BASE_SECONDS = 0.5
BACKOFF_MAX_SECONDS = 8.0
RETRY_AFTER_MAX_SECONDS = 60.0


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Why a transport should repeat a request, and how long to wait first."""

    reason: str
    delay_seconds: float


class RetryPolicy:
    """Decide whether a failed attempt is repeated.

    Args:
        max_retries: Repeats allowed after the first attempt.
        random_fraction: Source of jitter, returning a float in ``[0, 1)``.
            Tests inject a constant to make delays predictable.
    """

    def __init__(
        self,
        max_retries: int,
        *,
        random_fraction: Callable[[], float] | None = None,
    ) -> None:
        self.max_retries = max_retries
        # Jitter spreads retries of concurrent clients; it needs no cryptographic quality.
        self._random_fraction = random_fraction if random_fraction is not None else random.random

    @property
    def max_attempts(self) -> int:
        """First attempt plus the allowed repeats."""
        return self.max_retries + 1

    def after_exception(self, exc: APIConnectionError, attempt: int) -> RetryDecision | None:
        """Decision after attempt number ``attempt`` failed with ``exc``. ``None`` means give up.

        Only failures that happened before the request reached the API are
        repeated; a dropped connection while reading the response is not.
        """
        if not exc.retryable or attempt >= self.max_attempts:
            return None
        cause = exc.__cause__
        reason = type(cause).__name__ if cause is not None else type(exc).__name__
        return RetryDecision(reason=reason, delay_seconds=self.backoff(attempt))

    def after_response(self, response: httpx.Response, attempt: int) -> RetryDecision | None:
        """Decision after attempt number ``attempt`` received ``response``. ``None`` means accept it.

        502 and 503 come from the gateway before the application answers and
        are repeated, waiting for ``Retry-After`` when the gateway sends one
        and with backoff otherwise. A 504 is not: the application may still be
        processing, and billing, the request. A 429 is repeated only when it
        is the per-minute limit, waiting for ``Retry-After``; quota errors are
        never repeated.
        """
        if attempt >= self.max_attempts:
            return None
        status_code = response.status_code
        if status_code in RETRYABLE_STATUS_CODES:
            return RetryDecision(
                reason=f"HTTP {status_code}",
                delay_seconds=self._retry_after_delay(response, attempt),
            )
        if (
            status_code == PER_MINUTE_LIMIT_STATUS
            and response_error_code(response) == RATE_LIMIT_CODE
        ):
            return RetryDecision(
                reason=f"HTTP {status_code} {RATE_LIMIT_CODE}",
                delay_seconds=self._retry_after_delay(response, attempt),
            )
        return None

    def backoff(self, attempt: int) -> float:
        """Delay before the attempt that follows ``attempt``: exponential, capped and jittered.

        The nominal delay starts at half a second and doubles each time, up to
        eight seconds; jitter keeps between half and all of it.
        """
        nominal = min(BACKOFF_MAX_SECONDS, BACKOFF_BASE_SECONDS * 2.0 ** (attempt - 1))
        return nominal * (0.5 + 0.5 * self._random_fraction())

    def _retry_after_delay(self, response: httpx.Response, attempt: int) -> float:
        seconds = parse_retry_after(response.headers.get(RETRY_AFTER_HEADER))
        if seconds is None:
            return self.backoff(attempt)
        return min(float(seconds), RETRY_AFTER_MAX_SECONDS)
