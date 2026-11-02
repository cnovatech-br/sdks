"""Fixtures shared by the core test suite."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from cnovatech.sdk_core.config import ClientConfig, ProductSettings, build_client_config
from cnovatech.sdk_core.transport import AsyncTransport, SyncTransport

EXAMPLE_PRODUCT = ProductSettings(
    distribution_name="cnovatech-example",
    version="1.2.3",
    env_prefix="EXAMPLE_",
    default_base_url="https://api.example.test",
)

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def product() -> ProductSettings:
    return EXAMPLE_PRODUCT


@pytest.fixture
def config() -> ClientConfig:
    return build_client_config(EXAMPLE_PRODUCT, api_key="ex_test_key", environ={})


@pytest.fixture
def config_without_key() -> ClientConfig:
    return build_client_config(EXAMPLE_PRODUCT, environ={})


@pytest.fixture
def sent_requests() -> list[httpx.Request]:
    """Requests captured by transports built with ``make_sync_transport`` or ``make_async_transport``."""
    return []


@pytest.fixture
def make_sync_transport(
    config: ClientConfig, sent_requests: list[httpx.Request]
) -> Callable[..., SyncTransport]:
    def factory(handler: Handler, *, transport_config: ClientConfig | None = None) -> SyncTransport:
        def recording_handler(request: httpx.Request) -> httpx.Response:
            sent_requests.append(request)
            return handler(request)

        return SyncTransport(
            transport_config or config, transport=httpx.MockTransport(recording_handler)
        )

    return factory


@pytest.fixture
def make_async_transport(
    config: ClientConfig, sent_requests: list[httpx.Request]
) -> Callable[..., AsyncTransport]:
    def factory(
        handler: Handler, *, transport_config: ClientConfig | None = None
    ) -> AsyncTransport:
        def recording_handler(request: httpx.Request) -> httpx.Response:
            sent_requests.append(request)
            return handler(request)

        return AsyncTransport(
            transport_config or config, transport=httpx.MockTransport(recording_handler)
        )

    return factory


@pytest.fixture
def json_response() -> Callable[..., Handler]:
    """Build a handler that answers every request with the same JSON response."""

    def factory(
        status_code: int, payload: Any, *, headers: dict[str, str] | None = None
    ) -> Handler:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code, json=payload, headers=headers)

        return handler

    return factory
