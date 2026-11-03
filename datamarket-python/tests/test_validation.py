"""Validation rules specific to the Data Market API."""

from __future__ import annotations

import pytest

from cnovatech.datamarket import errors
from cnovatech.datamarket.resources._validation import validate_ean, validate_state


@pytest.mark.parametrize(
    "code", ["78949000", "12345678901", "789490001151", "7894900011517", " 12345678901234 "]
)
def test_valid_eans(code: str) -> None:
    assert validate_ean(code) == code.strip()


@pytest.mark.parametrize(
    "code", ["", "1234567", "123456789", "1234567890", "123456789012345", "78949000O1151"]
)
def test_invalid_eans(code: str) -> None:
    with pytest.raises(errors.InvalidRequestError, match="ean must contain only digits"):
        validate_ean(code)


def test_state_is_upper_cased_and_none_passes() -> None:
    assert validate_state("sp") == "SP"
    assert validate_state(" rj ") == "RJ"
    assert validate_state(None) is None


@pytest.mark.parametrize("value", ["", "S", "SPP", "S1", "ÇA"])
def test_invalid_states(value: str) -> None:
    with pytest.raises(errors.InvalidRequestError, match="two-letter state code"):
        validate_state(value)
