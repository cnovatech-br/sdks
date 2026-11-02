"""Exceptions raised by the Data Market SDK.

Catch :class:`DataMarketError` to handle anything the SDK raises, or one of
its subclasses for a specific situation::

    from cnovatech.datamarket import DataMarket, errors

    try:
        client.health()
    except errors.APITimeoutError:
        ...  # may have been billed; do not blindly repeat
    except errors.DataMarketError as exc:
        print(exc)
"""

from __future__ import annotations

from cnovatech.sdk_core.errors import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    BudgetExceededError,
    CnovatechError as DataMarketError,
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
)

__all__ = [
    "APIConnectionError",
    "APIStatusError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "BudgetExceededError",
    "ConfigurationError",
    "DataMarketError",
    "FieldError",
    "NotFoundError",
    "PermissionDeniedError",
    "QuotaExceededError",
    "RateLimitError",
    "ServerError",
    "TrialExpiredError",
    "UnexpectedResponseError",
    "UnprocessableEntityError",
]
