from __future__ import annotations

import pytest

from cnovatech.sdk_core.errors import CnovatechError, InvalidRequestError
from cnovatech.sdk_core.validation import (
    validate_batch,
    validate_identifier,
    validate_limit,
    validate_page,
    validate_path_segment,
    validate_product_code,
    validate_state,
)


def test_invalid_request_error_is_a_value_error_and_an_sdk_error() -> None:
    assert issubclass(InvalidRequestError, ValueError)
    assert issubclass(InvalidRequestError, CnovatechError)


@pytest.mark.parametrize(
    "code", ["78949000", "7894900011517", " 7894900011517 ", "12345678901234", "12345678901"]
)
def test_valid_product_codes(code: str) -> None:
    assert validate_product_code(code) == code.strip()


@pytest.mark.parametrize(
    "code",
    [
        "",
        "1234567",
        "123456789",
        "1234567890",
        "123456789012345",
        "7894900O11517",
        "٧٨٩٤٩٠٠٠١١٥١٧",
        "78949000-11517",
    ],
)
def test_invalid_product_codes(code: str) -> None:
    with pytest.raises(InvalidRequestError, match="code must contain only digits"):
        validate_product_code(code)


def test_product_code_error_names_the_argument() -> None:
    with pytest.raises(InvalidRequestError, match="competitor_code"):
        validate_product_code("x", name="competitor_code")


def test_batch_is_stripped_and_bounded() -> None:
    assert validate_batch([" a ", "b"], name="codes", maximum=2) == ["a", "b"]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ([], "must not be empty"),
        (["a", "b", "c"], "at most 2 entries"),
        ("ab", "must be a list"),
        (["a", ""], r"codes\[1\] must be a non-empty string"),
        (["a", 3], r"codes\[1\] must be a non-empty string"),
    ],
)
def test_invalid_batches(values: object, message: str) -> None:
    with pytest.raises(InvalidRequestError, match=message):
        validate_batch(values, name="codes", maximum=2)  # type: ignore[arg-type]


def test_identifier_is_canonicalised() -> None:
    assert (
        validate_identifier(" 0F8C7D2E6B1A4F3E9C5D2A7B8E1F4C63 ", name="store_id")
        == "0f8c7d2e-6b1a-4f3e-9c5d-2a7b8e1f4c63"
    )


@pytest.mark.parametrize("value", ["", "not-a-uuid", "123", "../../etc/passwd"])
def test_invalid_identifiers(value: str) -> None:
    with pytest.raises(InvalidRequestError, match="store_id must be the identifier"):
        validate_identifier(value, name="store_id")


def test_state_is_upper_cased_and_none_passes() -> None:
    assert validate_state("sp") == "SP"
    assert validate_state(" rj ") == "RJ"
    assert validate_state(None) is None


@pytest.mark.parametrize("value", ["", "S", "SPP", "S1", "ÇA"])
def test_invalid_states(value: str) -> None:
    with pytest.raises(InvalidRequestError, match="two-letter state code"):
        validate_state(value)


def test_path_segment_is_percent_encoded() -> None:
    assert validate_path_segment("Coca-Cola / Zero?", name="brand") == "Coca-Cola%20%2F%20Zero%3F"
    assert validate_path_segment("../x", name="brand") == "..%2Fx"


def test_empty_path_segment_is_rejected() -> None:
    with pytest.raises(InvalidRequestError, match="brand must be a non-empty string"):
        validate_path_segment("  ", name="brand")


@pytest.mark.parametrize("page", [0, -1, True, 1.5, "2"])
def test_invalid_pages(page: object) -> None:
    with pytest.raises(InvalidRequestError, match="page must be an integer"):
        validate_page(page)  # type: ignore[arg-type]


def test_valid_page_and_limit() -> None:
    assert validate_page(1) == 1
    assert validate_limit(100, maximum=100) == 100


@pytest.mark.parametrize("limit", [0, 101, True, "50"])
def test_invalid_limits(limit: object) -> None:
    with pytest.raises(InvalidRequestError, match="limit must be an integer between 1 and 100"):
        validate_limit(limit, maximum=100)  # type: ignore[arg-type]
