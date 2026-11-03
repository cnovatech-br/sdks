"""Validation of arguments specific to the Data Market API, before anything is sent."""

from __future__ import annotations

from cnovatech.sdk_core.errors import InvalidRequestError
from cnovatech.sdk_core.validation import stripped, validate_digits

EAN_LENGTHS = frozenset({8, 11, 12, 13, 14})
"""Lengths the catalogue accepts for a product code."""

STATE_CODE_LENGTH = 2


def validate_ean(value: str) -> str:
    """A product code as the catalogue spells it: digits only, 8 or 11 to 14 of them."""
    return validate_digits(value, lengths=EAN_LENGTHS, name="ean")


def validate_state(value: str | None, *, name: str = "state") -> str | None:
    """A two-letter Brazilian state code, upper-cased; ``None`` passes through."""
    if value is None:
        return None
    candidate = stripped(value)
    if len(candidate) != STATE_CODE_LENGTH or not candidate.isascii() or not candidate.isalpha():
        raise InvalidRequestError(
            f"{name} must be a two-letter state code such as 'SP'; got {value!r}."
        )
    return candidate.upper()
