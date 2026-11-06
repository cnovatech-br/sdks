"""Exceptions raised by the Data Market SDK.

Catch :class:`DataMarketError` to handle anything the SDK raises, or one of
its subclasses for a specific situation::

    from cnovatech.datamarket import DataMarket, errors

    try:
        product = client.products.get("7894900011517")
    except errors.EANNotFoundError as exc:
        print(exc.hint)
    except errors.APITimeoutError:
        ...  # may have been billed; do not blindly repeat
    except errors.DataMarketError as exc:
        print(exc)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    InvalidRequestError,
    NotFoundError,
    PermissionDeniedError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    TrialExpiredError,
    UnexpectedResponseError,
    UnprocessableEntityError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .models.stores import Store

__all__ = [
    "APIConnectionError",
    "APIStatusError",
    "APITimeoutError",
    "AmbiguousStoreError",
    "AuthenticationError",
    "BadRequestError",
    "BudgetExceededError",
    "ConfigurationError",
    "DataMarketError",
    "EANNotFoundError",
    "FieldError",
    "FilterRequiredError",
    "InvalidRequestError",
    "NotFoundError",
    "PermissionDeniedError",
    "QuotaExceededError",
    "RateLimitError",
    "ServerError",
    "StoreNotFoundError",
    "TrialExpiredError",
    "UnexpectedResponseError",
    "UnprocessableEntityError",
]


class EANNotFoundError(NotFoundError):
    """404 ``ean_not_found``: the code is not in the catalogue. The call is not billed.

    :attr:`hint` carries the API's suggestion, usually to check coverage of a
    whole list with ``products.coverage()`` or to search the catalogue.
    """

    @property
    def ean(self) -> str | None:
        """The code that was looked up, as reported by the API."""
        return self._body_text("ean")


class StoreNotFoundError(NotFoundError):
    """404 on a ``/stores/{store_id}`` route, or ``stores.find()`` without a match.

    On ``stores.compare()`` the unknown identifier may be the ``competitor_id``.
    """


class FilterRequiredError(BadRequestError):
    """400 ``filter_required``: beyond page 20 the catalogue needs at least one filter."""


class AmbiguousStoreError(DataMarketError):
    """``stores.find()`` matched more than one store and none by exact name.

    Attributes:
        name: The name that was searched.
        candidates: The stores that matched, so the caller can pick one.
    """

    def __init__(self, name: str, candidates: Sequence[Store]) -> None:
        names = ", ".join(repr(candidate.store_name) for candidate in candidates[:5])
        more = f" and {len(candidates) - 5} more" if len(candidates) > 5 else ""
        super().__init__(
            f"{name!r} matches {len(candidates)} stores and none by exact name: {names}{more}. "
            "Add state= or city=, or pick one of the candidates by store_id."
        )
        self.name = name
        self.candidates = list(candidates)

    def __reduce__(self) -> tuple[Any, ...]:
        return type(self), (self.name, self.candidates), self.__dict__
