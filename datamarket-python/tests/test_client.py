from __future__ import annotations

import re
from typing import Any

import httpx
import pytest

from cnovatech.datamarket import AsyncDataMarket, DataMarket, __version__, errors, models


def test_health_is_parsed_and_sent_without_credentials(health_payload: dict[str, Any]) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=health_payload, headers={"X-Correlation-ID": "corr-123"})

    with DataMarket(api_key="dm_secret", transport=httpx.MockTransport(handler)) as client:
        health = client.health()

    assert isinstance(health, models.Health)
    assert health.healthy is True
    assert health.cache == "degraded"
    assert health.version == "1.0.0"
    assert health.request_info is not None
    assert health.request_info.correlation_id == "corr-123"

    request = requests[0]
    assert str(request.url) == "https://datamarket.cnovatech.com.br/health"
    assert "X-API-Key" not in request.headers
    assert request.headers["User-Agent"].startswith("cnovatech-datamarket/")
    assert "dm_secret" not in request.headers["User-Agent"]


def test_health_works_without_an_api_key(health_payload: dict[str, Any]) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=health_payload))

    with DataMarket(transport=transport) as client:
        assert client.health().status == "healthy"


def test_unhealthy_status_is_reported_not_raised(health_payload: dict[str, Any]) -> None:
    payload = {**health_payload, "status": "unhealthy", "database": "disconnected"}
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=payload))

    with DataMarket(transport=transport) as client:
        health = client.health()

    assert health.healthy is False
    assert health.database == "disconnected"


async def test_async_health(health_payload: dict[str, Any]) -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json=health_payload))

    async with AsyncDataMarket(transport=transport) as client:
        health = await client.health()

    assert health.healthy is True
    assert health.request_info is not None
    assert health.request_info.path == "/health"


def test_base_url_from_environment(
    monkeypatch: pytest.MonkeyPatch, health_payload: dict[str, Any]
) -> None:
    monkeypatch.setenv("DATAMARKET_BASE_URL", "http://localhost:8000/")
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=health_payload)

    with DataMarket(transport=httpx.MockTransport(handler)) as client:
        assert client.base_url == "http://localhost:8000"
        client.health()

    assert str(requests[0].url) == "http://localhost:8000/health"


def test_invalid_base_url_is_a_configuration_error() -> None:
    with pytest.raises(errors.ConfigurationError, match="https"):
        DataMarket(base_url="http://datamarket.cnovatech.com.br")


def test_repr_masks_the_api_key() -> None:
    with DataMarket(api_key="dm_1234567890abcdef") as client:
        text = repr(client)

    assert text == "DataMarket(base_url='https://datamarket.cnovatech.com.br', api_key='dm_****')"


async def test_async_repr_masks_the_api_key() -> None:
    async with AsyncDataMarket(api_key="dm_1234567890abcdef") as client:
        text = repr(client)

    assert (
        text == "AsyncDataMarket(base_url='https://datamarket.cnovatech.com.br', api_key='dm_****')"
    )


def test_html_instead_of_json_is_a_typed_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<!doctype html>", headers={"Content-Type": "text/html"})

    with (
        DataMarket(transport=httpx.MockTransport(handler)) as client,
        pytest.raises(errors.UnexpectedResponseError) as excinfo,
    ):
        client.health()

    assert isinstance(excinfo.value, errors.DataMarketError)


def test_injected_http_client_is_left_open(health_payload: dict[str, Any]) -> None:
    http_client = httpx.Client(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json=health_payload))
    )

    with DataMarket(http_client=http_client) as client:
        client.health()

    assert http_client.is_closed is False
    http_client.close()


def test_every_error_derives_from_data_market_error() -> None:
    for name in errors.__all__:
        candidate = getattr(errors, name)
        if isinstance(candidate, type) and issubclass(candidate, BaseException):
            assert issubclass(candidate, errors.DataMarketError), name


def test_version_is_a_pep_440_string() -> None:
    assert re.match(r"^\d+\.\d+\.\d+", __version__), __version__
