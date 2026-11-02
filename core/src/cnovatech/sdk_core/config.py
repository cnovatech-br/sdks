"""Client configuration shared by every Cnovatech SDK.

A product SDK describes itself once through :class:`ProductSettings`. The core
combines that with the constructor arguments and the environment into an
immutable :class:`ClientConfig`, validating everything before any request is
sent.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr

from .errors import APIStatusError, ConfigurationError
from .metadata import read_distribution_version

if TYPE_CHECKING:
    from collections.abc import Mapping

CORE_DISTRIBUTION_NAME = "cnovatech-sdk-core"

DEFAULT_READ_TIMEOUT_SECONDS = 150.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10.0
DEFAULT_WRITE_TIMEOUT_SECONDS = 10.0
DEFAULT_POOL_TIMEOUT_SECONDS = 10.0
# The server closes any request that runs longer than this.
MAX_READ_TIMEOUT_SECONDS = 300.0
DEFAULT_MAX_RETRIES = 2

API_KEY_ENV_SUFFIX = "API_KEY"
BASE_URL_ENV_SUFFIX = "BASE_URL"

_LOOPBACK_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})
_MASK_PREFIX_MAX_LENGTH = 4


@dataclass(frozen=True, slots=True)
class ProductSettings:
    """What a product SDK tells the core about itself.

    Attributes:
        distribution_name: Name on PyPI. Appears in the ``User-Agent`` header.
        version: Installed version of the product SDK.
        env_prefix: Prefix of the environment variables the client reads,
            for example ``"DATAMARKET_"``.
        default_base_url: Production origin of the API, without a trailing slash.
        api_prefix: Path prefix shared by the authenticated endpoints.
        api_key_header: Header that carries the API key.
        error_overrides: Exception classes to raise for specific error codes,
            in place of the class chosen by HTTP status.
    """

    distribution_name: str
    version: str
    env_prefix: str
    default_base_url: str
    api_prefix: str = "/api/v1"
    api_key_header: str = "X-API-Key"
    error_overrides: Mapping[str, type[APIStatusError]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClientConfig:
    """Validated settings of one client instance. Build it with :func:`build_client_config`."""

    product: ProductSettings
    api_key: SecretStr | None
    base_url: str
    timeout: httpx.Timeout
    max_retries: int
    max_units_per_request: int | None

    @property
    def hostname(self) -> str:
        """Host part of ``base_url``, safe to show in messages."""
        return urlsplit(self.base_url).hostname or self.base_url

    @property
    def read_timeout_seconds(self) -> float:
        """Read timeout in seconds. :func:`build_timeout` guarantees it is set."""
        read_timeout = self.timeout.read
        if read_timeout is None:
            raise ConfigurationError("The read timeout must be set.")
        return float(read_timeout)

    @property
    def user_agent(self) -> str:
        """Identify the product SDK, the core, Python and httpx, in that order."""
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        core_version = read_distribution_version(CORE_DISTRIBUTION_NAME)
        return (
            f"{self.product.distribution_name}/{self.product.version} "
            f"{CORE_DISTRIBUTION_NAME}/{core_version} "
            f"python/{python_version} httpx/{httpx.__version__}"
        )

    @property
    def masked_api_key(self) -> str:
        """The API key as it may appear in ``repr`` and logs."""
        return mask_api_key(self.api_key)


def mask_api_key(api_key: SecretStr | None) -> str:
    """Redact a key, keeping only a short public prefix such as ``dm_****``."""
    if api_key is None:
        return "<not set>"
    prefix, separator, _ = api_key.get_secret_value().partition("_")
    if separator and 0 < len(prefix) <= _MASK_PREFIX_MAX_LENGTH:
        return f"{prefix}_****"
    return "****"


def build_client_config(
    product: ProductSettings,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float | httpx.Timeout = DEFAULT_READ_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    max_units_per_request: int | None = None,
    environ: Mapping[str, str] | None = None,
) -> ClientConfig:
    """Resolve and validate the settings of a client.

    Explicit arguments win over environment variables, which win over the
    product defaults. ``environ`` replaces ``os.environ`` in tests.

    Raises:
        ConfigurationError: A value is invalid. Nothing has been sent.
    """
    env = os.environ if environ is None else environ
    api_key_from_env = env.get(product.env_prefix + API_KEY_ENV_SUFFIX)
    base_url_from_env = env.get(product.env_prefix + BASE_URL_ENV_SUFFIX)
    return ClientConfig(
        product=product,
        api_key=_resolve_api_key(api_key, api_key_from_env),
        base_url=validate_base_url(base_url or base_url_from_env or product.default_base_url),
        timeout=build_timeout(timeout),
        max_retries=_validate_max_retries(max_retries),
        max_units_per_request=_validate_max_units_per_request(max_units_per_request),
    )


def validate_base_url(base_url: str) -> str:
    """Normalise a base URL and reject anything the client must not talk to.

    The URL must be absolute, name a host, and use HTTPS. Plain HTTP is accepted
    only for loopback addresses, so a local API can be used in development
    without ever sending a key in clear text over a network.
    """
    candidate = base_url.strip().rstrip("/")
    parts = urlsplit(candidate)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ConfigurationError(
            f"base_url must be an absolute http(s) URL with a host, got {base_url!r}."
        )
    if parts.query or parts.fragment:
        raise ConfigurationError("base_url must not carry a query string or fragment.")
    if parts.scheme == "http" and parts.hostname not in _LOOPBACK_HOSTNAMES:
        raise ConfigurationError(
            f"base_url must use https; plain http is only accepted for loopback, got {base_url!r}."
        )
    return candidate


def build_timeout(timeout: float | httpx.Timeout) -> httpx.Timeout:
    """Turn the constructor's ``timeout`` into a complete httpx timeout.

    A number sets the read timeout only; connect, write and pool keep their
    defaults. An ``httpx.Timeout`` is used as given. The read timeout must be
    greater than zero and at most :data:`MAX_READ_TIMEOUT_SECONDS`.
    """
    if isinstance(timeout, httpx.Timeout):
        resolved = timeout
    else:
        try:
            read_seconds = float(timeout)
        except (TypeError, ValueError) as exc:
            raise ConfigurationError(
                f"timeout must be a number of seconds or an httpx.Timeout, got {timeout!r}."
            ) from exc
        resolved = httpx.Timeout(
            connect=DEFAULT_CONNECT_TIMEOUT_SECONDS,
            read=read_seconds,
            write=DEFAULT_WRITE_TIMEOUT_SECONDS,
            pool=DEFAULT_POOL_TIMEOUT_SECONDS,
        )
    read_timeout = resolved.read
    if read_timeout is None or read_timeout <= 0 or read_timeout > MAX_READ_TIMEOUT_SECONDS:
        raise ConfigurationError(
            "The read timeout must be greater than 0 and at most "
            f"{MAX_READ_TIMEOUT_SECONDS:g} seconds, the server's own limit; got {read_timeout!r}."
        )
    return resolved


def _resolve_api_key(explicit: str | None, from_env: str | None) -> SecretStr | None:
    value = explicit if explicit is not None else from_env
    if value is None or not value.strip():
        return None
    return SecretStr(value.strip())


def _validate_max_retries(max_retries: int) -> int:
    if isinstance(max_retries, bool) or max_retries < 0:
        raise ConfigurationError(
            f"max_retries must be an integer of at least 0, got {max_retries!r}."
        )
    return max_retries


def _validate_max_units_per_request(max_units: int | None) -> int | None:
    if max_units is None:
        return None
    if isinstance(max_units, bool) or max_units < 1:
        raise ConfigurationError(
            f"max_units_per_request must be an integer of at least 1 or None, got {max_units!r}."
        )
    return max_units
