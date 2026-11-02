from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from cnovatech.sdk_core.config import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    DEFAULT_READ_TIMEOUT_SECONDS,
    MAX_READ_TIMEOUT_SECONDS,
    ProductSettings,
    build_client_config,
    mask_api_key,
)
from cnovatech.sdk_core.errors import ConfigurationError


def test_explicit_api_key_wins_over_environment(product: ProductSettings) -> None:
    config = build_client_config(
        product, api_key="ex_argument", environ={"EXAMPLE_API_KEY": "ex_environment"}
    )

    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "ex_argument"


def test_api_key_is_read_from_environment(product: ProductSettings) -> None:
    config = build_client_config(product, environ={"EXAMPLE_API_KEY": " ex_environment "})

    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "ex_environment"


@pytest.mark.parametrize("api_key", [None, "", "   "])
def test_blank_api_key_counts_as_missing(product: ProductSettings, api_key: str | None) -> None:
    config = build_client_config(product, api_key=api_key, environ={})

    assert config.api_key is None


def test_base_url_defaults_to_the_product(product: ProductSettings) -> None:
    config = build_client_config(product, environ={})

    assert config.base_url == "https://api.example.test"
    assert config.hostname == "api.example.test"


def test_base_url_from_environment_loses_trailing_slash(product: ProductSettings) -> None:
    config = build_client_config(
        product, environ={"EXAMPLE_BASE_URL": "https://staging.example.test/"}
    )

    assert config.base_url == "https://staging.example.test"


def test_explicit_base_url_wins_over_environment(product: ProductSettings) -> None:
    config = build_client_config(
        product,
        base_url="https://explicit.example.test",
        environ={"EXAMPLE_BASE_URL": "https://staging.example.test"},
    )

    assert config.base_url == "https://explicit.example.test"


@pytest.mark.parametrize(
    "base_url",
    [
        "http://api.example.test",
        "ftp://api.example.test",
        "api.example.test",
        "https://",
        "https://api.example.test/?debug=1",
        "https://api.example.test/#fragment",
    ],
)
def test_invalid_base_url_is_rejected(product: ProductSettings, base_url: str) -> None:
    with pytest.raises(ConfigurationError, match="base_url"):
        build_client_config(product, base_url=base_url, environ={})


@pytest.mark.parametrize("base_url", ["http://localhost:8000", "http://127.0.0.1:8000/"])
def test_plain_http_is_accepted_for_loopback(product: ProductSettings, base_url: str) -> None:
    config = build_client_config(product, base_url=base_url, environ={})

    assert config.base_url == base_url.rstrip("/")


def test_numeric_timeout_sets_the_read_phase_only(product: ProductSettings) -> None:
    config = build_client_config(product, timeout=42, environ={})

    assert config.timeout.read == 42.0
    assert config.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS
    assert config.read_timeout_seconds == 42.0


def test_default_timeout(product: ProductSettings) -> None:
    config = build_client_config(product, environ={})

    assert config.timeout.read == DEFAULT_READ_TIMEOUT_SECONDS


def test_httpx_timeout_is_used_as_given(product: ProductSettings) -> None:
    timeout = httpx.Timeout(connect=1.0, read=20.0, write=2.0, pool=3.0)

    config = build_client_config(product, timeout=timeout, environ={})

    assert config.timeout is timeout


@pytest.mark.parametrize(
    "timeout",
    [0, -1, MAX_READ_TIMEOUT_SECONDS + 1, httpx.Timeout(None), httpx.Timeout(10.0, read=None)],
)
def test_out_of_range_read_timeout_is_rejected(
    product: ProductSettings, timeout: float | httpx.Timeout
) -> None:
    with pytest.raises(ConfigurationError, match="read timeout"):
        build_client_config(product, timeout=timeout, environ={})


def test_non_numeric_timeout_is_rejected(product: ProductSettings) -> None:
    with pytest.raises(ConfigurationError, match="timeout must be a number"):
        build_client_config(product, timeout="soon", environ={})  # type: ignore[arg-type]


@pytest.mark.parametrize("max_retries", [-1, True])
def test_invalid_max_retries_is_rejected(product: ProductSettings, max_retries: int) -> None:
    with pytest.raises(ConfigurationError, match="max_retries"):
        build_client_config(product, max_retries=max_retries, environ={})


@pytest.mark.parametrize("max_units", [0, -5, True])
def test_invalid_max_units_per_request_is_rejected(
    product: ProductSettings, max_units: int
) -> None:
    with pytest.raises(ConfigurationError, match="max_units_per_request"):
        build_client_config(product, max_units_per_request=max_units, environ={})


def test_max_units_per_request_is_optional(product: ProductSettings) -> None:
    assert build_client_config(product, environ={}).max_units_per_request is None
    assert (
        build_client_config(product, max_units_per_request=5, environ={}).max_units_per_request == 5
    )


def test_user_agent_names_every_layer(product: ProductSettings) -> None:
    config = build_client_config(product, environ={})

    product_part, core_part, python_part, httpx_part = config.user_agent.split(" ")

    assert product_part == "cnovatech-example/1.2.3"
    assert core_part.startswith("cnovatech-sdk-core/")
    assert python_part.startswith("python/3.")
    assert httpx_part == f"httpx/{httpx.__version__}"


def test_api_key_never_appears_in_repr(product: ProductSettings) -> None:
    config = build_client_config(product, api_key="ex_very_secret", environ={})

    assert "ex_very_secret" not in repr(config)
    assert config.masked_api_key == "ex_****"


@pytest.mark.parametrize(
    ("raw_key", "masked"),
    [
        (None, "<not set>"),
        ("dm_1234567890", "dm_****"),
        ("no-separator", "****"),
        ("toolongprefix_abc", "****"),
    ],
)
def test_mask_api_key(raw_key: str | None, masked: str) -> None:
    assert mask_api_key(None if raw_key is None else SecretStr(raw_key)) == masked
