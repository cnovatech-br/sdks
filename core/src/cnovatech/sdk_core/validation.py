"""Local validation of request arguments. Everything here runs before any I/O.

The API validates every request itself and answers 422 without billing, so
the SDK checks only what makes a request malformed or unsafe to build: the
values that end up in the path, the page bounds, and the size of a batch.
Rules specific to one API, such as the accepted lengths of a product code,
are declared by the product SDK on top of the shapes defined here.
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Mapping
from urllib.parse import quote

from .errors import InvalidRequestError


def validate_digits(value: str, *, lengths: Collection[int], name: str) -> str:
    """A string of ASCII digits with one of the accepted lengths. Returns the value stripped."""
    candidate = stripped(value)
    if not (candidate.isascii() and candidate.isdigit()) or len(candidate) not in lengths:
        accepted = ", ".join(str(length) for length in sorted(lengths))
        raise InvalidRequestError(
            f"{name} must contain only digits, with one of these lengths: {accepted}; got {value!r}."
        )
    return candidate


def validate_batch(values: Iterable[str], *, name: str, maximum: int) -> list[str]:
    """A non-empty collection of strings with at most ``maximum`` entries, each stripped.

    Any iterable of strings is accepted, such as a list, a set, a tuple or a
    generator; a single string or a mapping is not.
    """
    if isinstance(values, (str, bytes, Mapping)) or not isinstance(values, Iterable):
        raise InvalidRequestError(f"{name} must be a list of strings.")
    items = list(values)
    if not items:
        raise InvalidRequestError(f"{name} must not be empty.")
    if len(items) > maximum:
        raise InvalidRequestError(
            f"{name} accepts at most {maximum} entries per call; got {len(items)}. "
            "Split the list and call again."
        )
    cleaned: list[str] = []
    for position, value in enumerate(items):
        if not stripped(value):
            raise InvalidRequestError(f"{name}[{position}] must be a non-empty string.")
        cleaned.append(stripped(value))
    return cleaned


def validate_identifier(value: str | uuid.UUID, *, name: str) -> str:
    """A UUID, as an object or in any accepted spelling, returned in its canonical form."""
    if isinstance(value, uuid.UUID):
        return str(value)
    try:
        return str(uuid.UUID(stripped(value)))
    except ValueError as exc:
        raise InvalidRequestError(
            f"{name} must be the identifier returned by the API (a UUID); got {value!r}."
        ) from exc


def validate_path_segment(value: str, *, name: str) -> str:
    """A non-empty value made safe for a URL path: every reserved character is percent-encoded."""
    candidate = stripped(value)
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


def stripped(value: object) -> str:
    """The value without surrounding whitespace, or an empty string when it is not text."""
    return value.strip() if isinstance(value, str) else ""
