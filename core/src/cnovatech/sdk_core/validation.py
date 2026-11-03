"""Local validation of request arguments. Everything here runs before any I/O.

The API validates every request itself and answers 422 without billing, so
the SDK checks only what makes a request malformed or unsafe to build: the
values that end up in the path, the page bounds, and the size of a batch.
Value ranges such as percentages are left to the API, whose answer carries
the field and the rule that failed.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from urllib.parse import quote

from .errors import InvalidRequestError

PRODUCT_CODE_LENGTHS = frozenset({8, 11, 12, 13, 14})


def validate_product_code(value: str, *, name: str = "code") -> str:
    """A GTIN: ASCII digits only, 8 or 11 to 14 of them. Returns the value stripped."""
    candidate = value.strip() if isinstance(value, str) else ""
    if (
        not (candidate.isascii() and candidate.isdigit())
        or len(candidate) not in PRODUCT_CODE_LENGTHS
    ):
        raise InvalidRequestError(
            f"{name} must contain only digits, 8 or 11 to 14 of them; got {value!r}."
        )
    return candidate


def validate_batch(values: Sequence[str], *, name: str, maximum: int) -> list[str]:
    """A non-empty list of strings with at most ``maximum`` entries, each stripped."""
    if isinstance(values, str) or not isinstance(values, Sequence):
        raise InvalidRequestError(f"{name} must be a list of strings.")
    if not values:
        raise InvalidRequestError(f"{name} must not be empty.")
    if len(values) > maximum:
        raise InvalidRequestError(
            f"{name} accepts at most {maximum} entries per call; got {len(values)}. "
            "Split the list and call again."
        )
    cleaned: list[str] = []
    for position, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise InvalidRequestError(f"{name}[{position}] must be a non-empty string.")
        cleaned.append(value.strip())
    return cleaned


def validate_identifier(value: str, *, name: str) -> str:
    """A UUID in any accepted spelling, returned in its canonical form."""
    try:
        return str(uuid.UUID(value.strip() if isinstance(value, str) else ""))
    except ValueError as exc:
        raise InvalidRequestError(
            f"{name} must be the identifier returned by the API (a UUID); got {value!r}."
        ) from exc


def validate_state(value: str | None, *, name: str = "state") -> str | None:
    """A two-letter state code, upper-cased; ``None`` passes through."""
    if value is None:
        return None
    candidate = value.strip() if isinstance(value, str) else ""
    if len(candidate) != 2 or not candidate.isascii() or not candidate.isalpha():
        raise InvalidRequestError(
            f"{name} must be a two-letter state code such as 'SP'; got {value!r}."
        )
    return candidate.upper()


def validate_path_segment(value: str, *, name: str) -> str:
    """A non-empty value made safe for a URL path: every reserved character is percent-encoded."""
    candidate = value.strip() if isinstance(value, str) else ""
    if not candidate:
        raise InvalidRequestError(f"{name} must be a non-empty string.")
    return quote(candidate, safe="")


def validate_page(page: int) -> int:
    """A page number starting at 1."""
    if isinstance(page, bool) or not isinstance(page, int) or page < 1:
        raise InvalidRequestError(f"page must be an integer of at least 1; got {page!r}.")
    return page


def validate_limit(limit: int, *, maximum: int) -> int:
    """A page size between 1 and the endpoint's maximum."""
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= maximum:
        raise InvalidRequestError(
            f"limit must be an integer between 1 and {maximum}; got {limit!r}."
        )
    return limit
