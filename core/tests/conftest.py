"""Fixtures shared by the core test suite."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from cnovatech.sdk_core.config import ClientConfig, ProductSettings, build_client_config
from cnovatech.sdk_core.retry import RetryPolicy
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
    """Requests captured by transports built with the factories below."""
    return []


@pytest.fixture
def sleeps() -> list[float]:
    """Delays the transports under test asked for, instead of sleeping."""
    return []


@pytest.fixture
def predictable_policy() -> Callable[[int], RetryPolicy]:
    """Retry policies whose jitter is fixed at its upper bound, so delays are the nominal ones."""
    return lambda max_retries: RetryPolicy(max_retries, random_fraction=lambda: 1.0)


@pytest.fixture
def make_sync_transport(
    config: ClientConfig,
    sent_requests: list[httpx.Request],
    sleeps: list[float],
    predictable_policy: Callable[[int], RetryPolicy],
) -> Callable[..., SyncTransport]:
    def factory(
        handler: Handler,
        *,
        transport_config: ClientConfig | None = None,
        max_retries: int | None = None,
    ) -> SyncTransport:
        def recording_handler(request: httpx.Request) -> httpx.Response:
            sent_requests.append(request)
            return handler(request)

        effective_config = transport_config or config
        retries = max_retries if max_retries is not None else effective_config.max_retries
        return SyncTransport(
            effective_config,
            transport=httpx.MockTransport(recording_handler),
            retry_policy=predictable_policy(retries),
            sleep=sleeps.append,
        )

    return factory


@pytest.fixture
def make_async_transport(
    config: ClientConfig,
    sent_requests: list[httpx.Request],
    sleeps: list[float],
    predictable_policy: Callable[[int], RetryPolicy],
) -> Callable[..., AsyncTransport]:
    def factory(
        handler: Handler,
        *,
        transport_config: ClientConfig | None = None,
        max_retries: int | None = None,
    ) -> AsyncTransport:
        def recording_handler(request: httpx.Request) -> httpx.Response:
            sent_requests.append(request)
            return handler(request)

        async def record_sleep(delay: float) -> None:
            sleeps.append(delay)

        effective_config = transport_config or config
        retries = max_retries if max_retries is not None else effective_config.max_retries
        return AsyncTransport(
            effective_config,
            transport=httpx.MockTransport(recording_handler),
            retry_policy=predictable_policy(retries),
            sleep=record_sleep,
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


@pytest.fixture
def sequence() -> Callable[..., Handler]:
    """Build a handler that answers consecutive requests from a list of responses or exceptions."""

    def factory(*outcomes: httpx.Response | Exception) -> Handler:
        remaining = list(outcomes)

        def handler(_request: httpx.Request) -> httpx.Response:
            outcome = remaining.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        return handler

    return factory
