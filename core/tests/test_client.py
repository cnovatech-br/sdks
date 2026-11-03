"""The client bases: configuration, transport, accounting and lifecycle shared by every product."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from conftest import EXAMPLE_PRODUCT, json_response, thing_payload

from cnovatech.sdk_core.client import BaseAsyncClient, BaseSyncClient
from cnovatech.sdk_core.errors import ConfigurationError
from cnovatech.sdk_core.models import APIResponse, Usage
from cnovatech.sdk_core.operation import Operation


class BilledThing(APIResponse):
    identifier: str
    name: str
    usage: Usage


def billed_operation() -> Operation[BilledThing]:
    return Operation(method="GET", path="/things/1", parse=BilledThing.model_validate)


class ExampleClient(BaseSyncClient):
    def __init__(self, api_key: str | None = None, **options: Any) -> None:
        super().__init__(EXAMPLE_PRODUCT, api_key, **options)

    def thing(self) -> BilledThing:
        return self._transport.execute(billed_operation())


class AsyncExampleClient(BaseAsyncClient):
    def __init__(self, api_key: str | None = None, **options: Any) -> None:
        super().__init__(EXAMPLE_PRODUCT, api_key, **options)

    async def thing(self) -> BilledThing:
        return await self._transport.execute(billed_operation())


def billed_transport(requests: list[httpx.Request]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return json_response(200, thing_payload(usage={"query_cost": 2, "remaining": 8}))(request)

    return httpx.MockTransport(handler)


def test_client_binds_the_product_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_API_KEY", "ex_from_env")
    requests: list[httpx.Request] = []

    with ExampleClient(transport=billed_transport(requests)) as client:
        thing = client.thing()

    assert client.base_url == "https://api.example.test"
    assert thing.name == "Milk"
    assert requests[0].headers["X-API-Key"] == "ex_from_env"
    assert requests[0].headers["User-Agent"].startswith("cnovatech-example/1.2.3 ")
    assert client.usage.spent == 2
    assert client.usage.last is not None
    assert client.usage.last.remaining == 8
    assert client.rate_limit.limit is None
    assert repr(client) == "ExampleClient(base_url='https://api.example.test', api_key='ex_****')"


def test_explicit_arguments_reach_the_configuration() -> None:
    client = ExampleClient(
        "ex_key", base_url="https://staging.example.test", timeout=5, max_retries=0
    )

    assert client.base_url == "https://staging.example.test"
    client.close()


def test_invalid_configuration_fails_at_construction() -> None:
    with pytest.raises(ConfigurationError, match="https"):
        ExampleClient("ex_key", base_url="http://api.example.test")


def test_leaving_the_context_closes_the_pool() -> None:
    with ExampleClient("ex_key", transport=billed_transport([])) as client:
        client.thing()

    with pytest.raises(RuntimeError):
        client.thing()


def test_injected_http_client_is_left_open() -> None:
    http_client = httpx.Client(transport=billed_transport([]))

    with ExampleClient("ex_key", http_client=http_client) as client:
        client.thing()

    assert http_client.is_closed is False
    http_client.close()


async def test_async_client_mirrors_the_synchronous_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXAMPLE_API_KEY", "ex_from_env")
    requests: list[httpx.Request] = []

    async with AsyncExampleClient(transport=billed_transport(requests)) as client:
        thing = await client.thing()

    assert thing.name == "Milk"
    assert requests[0].headers["X-API-Key"] == "ex_from_env"
    assert client.base_url == "https://api.example.test"
    assert client.usage.spent == 2
    assert client.rate_limit.remaining is None
    assert repr(client) == (
        "AsyncExampleClient(base_url='https://api.example.test', api_key='ex_****')"
    )

    with pytest.raises(RuntimeError):
        await client.thing()


async def test_async_injected_http_client_is_left_open() -> None:
    http_client = httpx.AsyncClient(transport=billed_transport([]))

    async with AsyncExampleClient("ex_key", http_client=http_client) as client:
        await client.thing()

    assert http_client.is_closed is False
    await http_client.aclose()
