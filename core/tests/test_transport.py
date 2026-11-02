from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from pydantic import ConfigDict

from cnovatech.sdk_core.config import ClientConfig, ProductSettings, build_client_config
from cnovatech.sdk_core.errors import (
    APIConnectionError,
    APITimeoutError,
    ConfigurationError,
    NotFoundError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    UnexpectedResponseError,
)
from cnovatech.sdk_core.models import APIResponse, Health, parser_for
from cnovatech.sdk_core.operation import Operation
from cnovatech.sdk_core.transport import AsyncTransport, SyncTransport, prepare_request

if TYPE_CHECKING:
    from collections.abc import Callable

HEALTH_PAYLOAD = {
    "status": "healthy",
    "database": "connected",
    "cache": "healthy",
    "timestamp": "2026-11-02T21:46:19+00:00",
    "version": "1.0.0",
}


class Thing(APIResponse):
    identifier: str
    name: str


class StrictThing(APIResponse):
    model_config = ConfigDict(frozen=True, extra="forbid")

    identifier: str


def thing_operation(**params: Any) -> Operation[Thing]:
    return Operation(method="GET", path="/things/1", parse=parser_for(Thing), params=params)


def health_operation() -> Operation[Health]:
    return Operation(
        method="GET",
        path="/health",
        parse=parser_for(Health),
        requires_auth=False,
        under_api_prefix=False,
    )


def test_prepared_request_for_an_authenticated_call(config: ClientConfig) -> None:
    prepared = prepare_request(config, thing_operation(search="milk", state=None, limit=10))

    assert prepared.method == "GET"
    assert prepared.url == "https://api.example.test/api/v1/things/1"
    assert prepared.path == "/api/v1/things/1"
    assert prepared.params == {"search": "milk", "limit": 10}
    assert prepared.headers["X-API-Key"] == "ex_test_key"
    assert prepared.headers["Accept"] == "application/json"
    assert prepared.headers["User-Agent"] == config.user_agent
    assert uuid.UUID(prepared.headers["X-Correlation-ID"]) is not None
    assert prepared.correlation_id == prepared.headers["X-Correlation-ID"]


def test_prepared_request_for_a_public_call_outside_the_prefix(config: ClientConfig) -> None:
    prepared = prepare_request(config, health_operation())

    assert prepared.url == "https://api.example.test/health"
    assert "X-API-Key" not in prepared.headers


def test_each_request_gets_its_own_correlation_id(config: ClientConfig) -> None:
    first = prepare_request(config, health_operation())
    second = prepare_request(config, health_operation())

    assert first.correlation_id != second.correlation_id


def test_custom_api_key_header(config: ClientConfig) -> None:
    product = ProductSettings(
        distribution_name="cnovatech-example",
        version="1.2.3",
        env_prefix="EXAMPLE_",
        default_base_url="https://api.example.test",
        api_key_header="Authorization",
    )
    custom = build_client_config(product, api_key="ex_test_key", environ={})

    prepared = prepare_request(custom, thing_operation())

    assert prepared.headers["Authorization"] == "ex_test_key"
    assert config.product.api_key_header == "X-API-Key"


def test_missing_api_key_fails_before_any_request(
    config_without_key: ClientConfig,
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
    json_response: Callable[..., Any],
) -> None:
    transport = make_sync_transport(json_response(200, {}), transport_config=config_without_key)

    with pytest.raises(ConfigurationError, match="EXAMPLE_API_KEY"):
        transport.execute(thing_operation())

    assert sent_requests == []


def test_public_call_works_without_api_key(
    config_without_key: ClientConfig,
    make_sync_transport: Callable[..., SyncTransport],
    json_response: Callable[..., Any],
) -> None:
    transport = make_sync_transport(
        json_response(200, HEALTH_PAYLOAD), transport_config=config_without_key
    )

    assert transport.execute(health_operation()).healthy is True


def test_successful_response_is_parsed_and_annotated(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
    json_response: Callable[..., Any],
) -> None:
    handler = json_response(
        200,
        {"identifier": "1", "name": "Milk", "introduced_later": True},
        headers={"X-Correlation-ID": "echoed-by-api"},
    )

    with make_sync_transport(handler) as transport:
        thing = transport.execute(thing_operation())

    assert thing.name == "Milk"
    assert thing.model_extra == {"introduced_later": True}
    assert thing.request_info is not None
    assert thing.request_info.method == "GET"
    assert thing.request_info.path == "/api/v1/things/1"
    assert thing.request_info.status_code == 200
    assert thing.request_info.correlation_id == "echoed-by-api"
    assert thing.request_info.attempts == 1
    assert thing.request_info.elapsed_seconds >= 0
    assert str(sent_requests[0].url) == "https://api.example.test/api/v1/things/1"


def test_correlation_id_falls_back_to_the_one_sent(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
    json_response: Callable[..., Any],
) -> None:
    transport = make_sync_transport(json_response(200, {"identifier": "1", "name": "Milk"}))

    thing = transport.execute(thing_operation())

    assert thing.request_info is not None
    assert thing.request_info.correlation_id == sent_requests[0].headers["X-Correlation-ID"]


def test_html_with_status_200_is_an_unexpected_response(
    make_sync_transport: Callable[..., SyncTransport],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, text="<!doctype html>", headers={"Content-Type": "text/html; charset=utf-8"}
        )

    with pytest.raises(UnexpectedResponseError, match="text/html") as excinfo:
        make_sync_transport(handler).execute(thing_operation())

    assert excinfo.value.status_code == 200
    assert excinfo.value.content_type == "text/html; charset=utf-8"


def test_invalid_json_is_an_unexpected_response(
    make_sync_transport: Callable[..., SyncTransport],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=b"{not json", headers={"Content-Type": "application/json"}
        )

    with pytest.raises(UnexpectedResponseError, match="not valid JSON"):
        make_sync_transport(handler).execute(thing_operation())


def test_payload_that_does_not_match_the_model_is_an_unexpected_response(
    make_sync_transport: Callable[..., SyncTransport],
    json_response: Callable[..., Any],
) -> None:
    operation: Operation[StrictThing] = Operation(
        method="GET", path="/things/1", parse=parser_for(StrictThing)
    )

    with pytest.raises(UnexpectedResponseError, match="did not match") as excinfo:
        make_sync_transport(json_response(200, {"identifier": "1", "surprise": True})).execute(
            operation
        )

    assert excinfo.value.__cause__ is not None


def test_error_status_raises_the_mapped_exception(
    make_sync_transport: Callable[..., SyncTransport],
    json_response: Callable[..., Any],
) -> None:
    handler = json_response(
        404,
        {"error": "thing_not_found", "message": "No such thing.", "what_to_do": "Try another."},
        headers={"X-Correlation-ID": "corr-404"},
    )

    with pytest.raises(NotFoundError) as excinfo:
        make_sync_transport(handler).execute(thing_operation())

    assert excinfo.value.code == "thing_not_found"
    assert excinfo.value.hint == "Try another."
    assert excinfo.value.correlation_id == "corr-404"


def test_product_error_overrides_are_applied(
    make_sync_transport: Callable[..., SyncTransport],
    json_response: Callable[..., Any],
) -> None:
    class ThingNotFoundError(NotFoundError):
        pass

    product = ProductSettings(
        distribution_name="cnovatech-example",
        version="1.2.3",
        env_prefix="EXAMPLE_",
        default_base_url="https://api.example.test",
        error_overrides={"thing_not_found": ThingNotFoundError},
    )
    custom = build_client_config(product, api_key="ex_test_key", environ={})
    handler = json_response(404, {"error": "thing_not_found", "message": "No such thing."})

    with pytest.raises(ThingNotFoundError):
        make_sync_transport(handler, transport_config=custom).execute(thing_operation())


@pytest.mark.parametrize(
    ("status_code", "payload", "headers", "expected"),
    [
        (429, {"error": "rate_limit_exceeded"}, {"Retry-After": "3"}, RateLimitError),
        (429, {"error": "monthly_limit_exceeded"}, {}, QuotaExceededError),
        (503, {"error": "service_unavailable"}, {}, ServerError),
    ],
)
def test_error_families(
    make_sync_transport: Callable[..., SyncTransport],
    json_response: Callable[..., Any],
    status_code: int,
    payload: dict[str, Any],
    headers: dict[str, str],
    expected: type[Exception],
) -> None:
    with pytest.raises(expected):
        make_sync_transport(json_response(status_code, payload, headers=headers)).execute(
            thing_operation()
        )


def test_connection_failure_is_wrapped(make_sync_transport: Callable[..., SyncTransport]) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(APIConnectionError, match=r"api\.example\.test: ConnectError") as excinfo:
        make_sync_transport(handler).execute(thing_operation())

    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)
    assert "ex_test_key" not in str(excinfo.value)


def test_timeout_is_wrapped_and_warns_about_billing(
    make_sync_transport: Callable[..., SyncTransport],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(APITimeoutError, match="150 seconds") as excinfo:
        make_sync_transport(handler).execute(thing_operation())

    assert "billed" in str(excinfo.value)
    assert isinstance(excinfo.value, APIConnectionError)


def test_close_leaves_an_injected_client_open(config: ClientConfig) -> None:
    http_client = httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(200)))

    transport = SyncTransport(config, http_client=http_client)
    transport.close()

    assert http_client.is_closed is False
    http_client.close()


def test_close_closes_the_client_it_created(config: ClientConfig) -> None:
    transport = SyncTransport(
        config, transport=httpx.MockTransport(lambda _request: httpx.Response(200))
    )

    with transport:
        pass

    with pytest.raises(RuntimeError):
        transport.execute(health_operation())


def test_http_client_and_transport_are_mutually_exclusive(config: ClientConfig) -> None:
    http_client = httpx.Client()
    try:
        with pytest.raises(ConfigurationError, match="not both"):
            SyncTransport(
                config,
                http_client=http_client,
                transport=httpx.MockTransport(lambda _r: httpx.Response(200)),
            )
        with pytest.raises(ConfigurationError, match="not both"):
            AsyncTransport(
                config,
                http_client=httpx.AsyncClient(),
                transport=httpx.MockTransport(lambda _r: httpx.Response(200)),
            )
    finally:
        http_client.close()


def test_transport_exposes_its_config(config: ClientConfig) -> None:
    transport = SyncTransport(
        config, transport=httpx.MockTransport(lambda _request: httpx.Response(200))
    )

    assert transport.config is config
    transport.close()


async def test_async_transport_parses_a_successful_response(
    make_async_transport: Callable[..., AsyncTransport],
    sent_requests: list[httpx.Request],
    json_response: Callable[..., Any],
) -> None:
    async with make_async_transport(json_response(200, HEALTH_PAYLOAD)) as transport:
        health = await transport.execute(health_operation())

    assert health.healthy is True
    assert health.request_info is not None
    assert health.request_info.path == "/health"
    assert str(sent_requests[0].url) == "https://api.example.test/health"


async def test_async_transport_raises_mapped_errors(
    make_async_transport: Callable[..., AsyncTransport],
    json_response: Callable[..., Any],
) -> None:
    transport = make_async_transport(json_response(404, {"error": "not_found", "message": "Nope."}))

    with pytest.raises(NotFoundError, match="Nope"):
        await transport.execute(thing_operation())
    await transport.aclose()


async def test_async_transport_wraps_timeouts(
    make_async_transport: Callable[..., AsyncTransport],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    async with make_async_transport(handler) as transport:
        with pytest.raises(APITimeoutError):
            await transport.execute(thing_operation())


async def test_async_transport_wraps_connection_failures(
    make_async_transport: Callable[..., AsyncTransport],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    async with make_async_transport(handler) as transport:
        with pytest.raises(APIConnectionError):
            await transport.execute(thing_operation())


async def test_async_close_leaves_an_injected_client_open(config: ClientConfig) -> None:
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200))
    )

    transport = AsyncTransport(config, http_client=http_client)
    await transport.aclose()

    assert http_client.is_closed is False
    assert transport.config is config
    await http_client.aclose()
