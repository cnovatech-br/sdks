"""Per-client accounting of quota usage and of the per-minute rate limit."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from .errors import parse_int
from .models import APIResponse, Usage

if TYPE_CHECKING:
    from collections.abc import Mapping

logger = logging.getLogger(__name__)

LOW_QUOTA_FRACTION = 0.1

RATE_LIMIT_LIMIT_HEADER = "X-RateLimit-Limit"
RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Remaining"
RATE_LIMIT_RESET_HEADER = "X-RateLimit-Reset"


class UsageTracker:
    """Accumulates the ``usage`` blocks of the responses one client received.

    Attributes:
        last: The most recent ``usage`` block, with the balance after that call.
        spent: Units consumed through this client since it was created, as
            reported by the API.
        calls: Billed responses recorded.
    """

    def __init__(self) -> None:
        self.last: Usage | None = None
        self.spent = 0
        self.calls = 0
        self._low_quota_warned = False

    def record(self, usage: Usage) -> None:
        """Record one billed response and warn once when the balance drops below 10%."""
        self.last = usage
        self.spent += usage.query_cost
        self.calls += 1
        self._warn_when_low(usage)

    def observe(self, usage: Usage | None) -> None:
        """Keep the balance reported with an error response, which billed nothing.

        A quota error is the moment the balance matters most; ``last`` reflects
        it even though no units were spent.
        """
        if usage is not None:
            self.last = usage

    def _warn_when_low(self, usage: Usage) -> None:
        if usage.limit is None or usage.remaining is None or usage.limit <= 0:
            self._low_quota_warned = False
            return
        is_low = usage.remaining < LOW_QUOTA_FRACTION * usage.limit
        if is_low and not self._low_quota_warned:
            logger.warning(
                "Quota is running low: %d of %d units remaining in this cycle",
                usage.remaining,
                usage.limit,
                extra={"remaining": usage.remaining, "limit": usage.limit},
            )
        self._low_quota_warned = is_low

    def __repr__(self) -> str:
        remaining = self.last.remaining if self.last is not None else None
        return f"UsageTracker(spent={self.spent}, calls={self.calls}, remaining={remaining})"


def record_usage(tracker: UsageTracker, result: object) -> None:
    """Record the ``usage`` block of a parsed response, when it carries one."""
    if not isinstance(result, APIResponse):
        return
    usage = getattr(result, "usage", None)
    if isinstance(usage, Usage):
        tracker.record(usage)


@dataclass(slots=True)
class RateLimitState:
    """The per-minute rate limit as last reported by the API's headers.

    Attributes:
        limit: Requests allowed per minute.
        remaining: Requests left in the current minute.
        reset_in_seconds: Seconds until the current minute ends.
        observed_at: When these values were received, in UTC.
    """

    limit: int | None = None
    remaining: int | None = None
    reset_in_seconds: int | None = None
    observed_at: datetime | None = None

    def update_from_headers(self, headers: Mapping[str, str]) -> None:
        """Read the ``X-RateLimit-*`` headers of a response, if present."""
        limit = parse_int(headers.get(RATE_LIMIT_LIMIT_HEADER))
        remaining = parse_int(headers.get(RATE_LIMIT_REMAINING_HEADER))
        if limit is None and remaining is None:
            return
        self.limit = limit
        self.remaining = remaining
        self.reset_in_seconds = parse_int(headers.get(RATE_LIMIT_RESET_HEADER))
        self.observed_at = datetime.now(timezone.utc)
