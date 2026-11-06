from __future__ import annotations

import uuid

import pytest

from cnovatech.sdk_core.errors import CnovatechError, InvalidRequestError
from cnovatech.sdk_core.validation import (
    stripped,
    validate_batch,
    validate_digits,
    validate_identifier,
    validate_limit,
    validate_page,
    validate_path_segment,
)

LENGTHS = frozenset({8, 13})


def test_invalid_request_error_is_a_value_error_and_an_sdk_error() -> None:
    assert issubclass(InvalidRequestError, ValueError)
    assert issubclass(InvalidRequestError, CnovatechError)


@pytest.mark.parametrize("code", ["78949000", "7894900011517", " 7894900011517 "])
def test_valid_digit_strings(code: str) -> None:
    assert validate_digits(code, lengths=LENGTHS, name="code") == code.strip()


@pytest.mark.parametrize(
    "code", ["", "1234567", "123456789", "7894900O11517", "٧٨٩٤٩٠٠٠١١٥١٧", "78949000-11517"]
)
def test_invalid_digit_strings(code: str) -> None:
    with pytest.raises(InvalidRequestError, match=r"code must contain only digits.*8, 13"):
        validate_digits(code, lengths=LENGTHS, name="code")


def test_digit_errors_name_the_argument() -> None:
    with pytest.raises(InvalidRequestError, match="competitor_code"):
        validate_digits("x", lengths=LENGTHS, name="competitor_code")


def test_batch_is_stripped_and_bounded() -> None:
    assert validate_batch([" a ", "b"], name="codes", maximum=2) == ["a", "b"]


def test_batch_accepts_any_iterable_of_strings() -> None:
    assert validate_batch(("a", "b"), name="codes", maximum=2) == ["a", "b"]
    assert validate_batch({"a"}, name="codes", maximum=2) == ["a"]
    assert validate_batch(iter(["a", "b"]), name="codes", maximum=2) == ["a", "b"]


@pytest.mark.parametrize(
    ("values", "message"),
    [
        ([], "must not be empty"),
        (["a", "b", "c"], "at most 2 entries"),
        ("ab", "must be a list"),
        (b"ab", "must be a list"),
        ({"a": 1}, "must be a list"),
        (3, "must be a list"),
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


def test_identifier_accepts_uuid_objects() -> None:
    identifier = uuid.UUID("0f8c7d2e-6b1a-4f3e-9c5d-2a7b8e1f4c63")

    assert validate_identifier(identifier, name="store_id") == str(identifier)


@pytest.mark.parametrize("value", ["", "not-a-uuid", "123", "../../etc/passwd"])
def test_invalid_identifiers(value: str) -> None:
    with pytest.raises(InvalidRequestError, match="store_id must be the identifier"):
        validate_identifier(value, name="store_id")


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


@pytest.mark.parametrize(("value", "expected"), [(" a ", "a"), ("", ""), (None, ""), (3, "")])
def test_stripped(value: object, expected: str) -> None:
    assert stripped(value) == expected
