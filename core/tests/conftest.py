"""Helpers and fixtures shared by the core test suite.

Stateless helpers are plain functions, imported where needed; fixtures are
reserved for what carries state between the test and the code under test.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import httpx
import pytest

from cnovatech.sdk_core.config import ClientConfig, ProductSettings, build_client_config
from cnovatech.sdk_core.models import APIResponse
from cnovatech.sdk_core.operation import Operation
from cnovatech.sdk_core.retry import RetryPolicy
from cnovatech.sdk_core.transport import AsyncTransport, SyncTransport

EXAMPLE_PRODUCT = ProductSettings(
    distribution_name="cnovatech-example",
    version="1.2.3",
    env_prefix="EXAMPLE_",
    default_base_url="https://api.example.test",
)

Handler = Callable[[httpx.Request], httpx.Response]


class Thing(APIResponse):
    identifier: str
    name: str


def thing_payload(**extra: Any) -> dict[str, Any]:
    return {"identifier": "1", "name": "Milk", **extra}


def thing_operation(**params: Any) -> Operation[Thing]:
    return Operation(method="GET", path="/things/1", parse=Thing.model_validate, params=params)


def ok() -> httpx.Response:
    return httpx.Response(200, json=thing_payload())


def json_response(
    status_code: int, payload: Any, *, headers: dict[str, str] | None = None
) -> Handler:
    """A handler that answers every request with the same JSON response."""

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=payload, headers=headers)

    return handler


def sequence(*outcomes: httpx.Response | Exception) -> Handler:
    """A handler that answers consecutive requests from a list of responses or exceptions."""
    remaining = list(outcomes)

    def handler(_request: httpx.Request) -> httpx.Response:
        outcome = remaining.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return handler


def predictable_policy(max_retries: int) -> RetryPolicy:
    """A retry policy whose jitter sits at its upper bound, so delays are the nominal ones."""
    return RetryPolicy(max_retries, random_fraction=lambda: 1.0)


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


def _recording(handler: Handler, sent_requests: list[httpx.Request]) -> httpx.MockTransport:
    def recording_handler(request: httpx.Request) -> httpx.Response:
        sent_requests.append(request)
        return handler(request)

    return httpx.MockTransport(recording_handler)


def _settings(
    default: ClientConfig, override: ClientConfig | None, max_retries: int | None
) -> tuple[ClientConfig, RetryPolicy]:
    effective = override or default
    retries = max_retries if max_retries is not None else effective.max_retries
    return effective, predictable_policy(retries)


@pytest.fixture
def make_sync_transport(
    config: ClientConfig, sent_requests: list[httpx.Request], sleeps: list[float]
) -> Callable[..., SyncTransport]:
    def factory(
        handler: Handler,
        *,
        transport_config: ClientConfig | None = None,
        max_retries: int | None = None,
    ) -> SyncTransport:
        effective, policy = _settings(config, transport_config, max_retries)
        return SyncTransport(
            effective,
            transport=_recording(handler, sent_requests),
            retry_policy=policy,
            sleep=sleeps.append,
        )

    return factory


@pytest.fixture
def make_async_transport(
    config: ClientConfig, sent_requests: list[httpx.Request], sleeps: list[float]
) -> Callable[..., AsyncTransport]:
    async def record_sleep(delay: float) -> None:
        sleeps.append(delay)

    def factory(
        handler: Handler,
        *,
        transport_config: ClientConfig | None = None,
        max_retries: int | None = None,
    ) -> AsyncTransport:
        effective, policy = _settings(config, transport_config, max_retries)
        return AsyncTransport(
            effective,
            transport=_recording(handler, sent_requests),
            retry_policy=policy,
            sleep=record_sleep,
        )

    return factory
