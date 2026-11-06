from __future__ import annotations

import dataclasses
import uuid
from typing import TYPE_CHECKING, Any

import httpx
import pytest
from conftest import EXAMPLE_PRODUCT, Thing, json_response, thing_operation, thing_payload
from pydantic import ConfigDict

from cnovatech.sdk_core.config import ClientConfig, build_client_config
from cnovatech.sdk_core.errors import (
    APIConnectionError,
    APITimeoutError,
    BudgetExceededError,
    ConfigurationError,
    NotFoundError,
    QuotaExceededError,
    RateLimitError,
    ServerError,
    UnexpectedResponseError,
)
from cnovatech.sdk_core.models import APIResponse
from cnovatech.sdk_core.operation import Operation
from cnovatech.sdk_core.transport import (
    AsyncTransport,
    SyncTransport,
    prepare_request,
    translate_transport_error,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class Status(APIResponse):
    status: str


class StrictThing(APIResponse):
    model_config = ConfigDict(frozen=True, extra="forbid")

    identifier: str


def status_operation() -> Operation[Status]:
    return Operation(
        method="GET",
        path="/status",
        parse=Status.model_validate,
        requires_auth=False,
        under_api_prefix=False,
    )


def costly_operation(estimated_cost: int) -> Operation[Thing]:
    return Operation(
        method="GET", path="/things", parse=Thing.model_validate, estimated_cost=estimated_cost
    )


# --- request preparation ----------------------------------------------------


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
    prepared = prepare_request(config, status_operation())

    assert prepared.url == "https://api.example.test/status"
    assert "X-API-Key" not in prepared.headers


def test_each_request_gets_its_own_correlation_id(config: ClientConfig) -> None:
    first = prepare_request(config, status_operation())
    second = prepare_request(config, status_operation())

    assert first.correlation_id != second.correlation_id


def test_prepared_request_repr_leaves_the_headers_out(config: ClientConfig) -> None:
    """Debuggers and ``pytest --showlocals`` print locals; the key must not be in them."""
    prepared = prepare_request(config, thing_operation())

    assert prepared.headers["X-API-Key"] == "ex_test_key"
    assert "ex_test_key" not in repr(prepared)
    assert "headers" not in repr(prepared)


def test_custom_api_key_header() -> None:
    product = dataclasses.replace(EXAMPLE_PRODUCT, api_key_header="Authorization")
    custom = build_client_config(product, api_key="ex_test_key", environ={})

    prepared = prepare_request(custom, thing_operation())

    assert prepared.headers["Authorization"] == "ex_test_key"


def test_missing_api_key_fails_before_any_request(
    config_without_key: ClientConfig,
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    transport = make_sync_transport(json_response(200, {}), transport_config=config_without_key)

    with pytest.raises(ConfigurationError, match="EXAMPLE_API_KEY"):
        transport.execute(thing_operation())

    assert sent_requests == []


def test_public_call_works_without_api_key(
    config_without_key: ClientConfig,
    make_sync_transport: Callable[..., SyncTransport],
) -> None:
    transport = make_sync_transport(
        json_response(200, {"status": "healthy"}), transport_config=config_without_key
    )

    assert transport.execute(status_operation()).status == "healthy"


def test_call_above_the_per_request_budget_is_refused_before_sending(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    capped = build_client_config(
        EXAMPLE_PRODUCT, api_key="ex_test_key", max_units_per_request=20, environ={}
    )
    transport = make_sync_transport(json_response(200, {}), transport_config=capped)

    with pytest.raises(BudgetExceededError, match="40 quota units") as excinfo:
        transport.execute(costly_operation(40))

    assert excinfo.value.estimated_cost == 40
    assert excinfo.value.limit == 20
    assert excinfo.value.spent == 0
    assert sent_requests == []


def test_call_within_the_per_request_budget_is_sent(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    capped = build_client_config(
        EXAMPLE_PRODUCT, api_key="ex_test_key", max_units_per_request=20, environ={}
    )
    transport = make_sync_transport(json_response(200, thing_payload()), transport_config=capped)

    transport.execute(costly_operation(20))

    assert len(sent_requests) == 1


def test_without_a_budget_any_cost_is_sent(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    make_sync_transport(json_response(200, thing_payload())).execute(costly_operation(10_000))

    assert len(sent_requests) == 1


# --- response interpretation ------------------------------------------------


def test_successful_response_is_parsed_and_annotated(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    handler = json_response(
        200, thing_payload(introduced_later=True), headers={"X-Correlation-ID": "echoed-by-api"}
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
) -> None:
    transport = make_sync_transport(json_response(200, thing_payload()))

    thing = transport.execute(thing_operation())

    assert thing.request_info is not None
    assert thing.request_info.correlation_id == sent_requests[0].headers["X-Correlation-ID"]


def test_error_without_echoed_correlation_id_keeps_the_one_sent(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            502, text="<html>Bad Gateway</html>", headers={"Content-Type": "text/html"}
        )

    with pytest.raises(ServerError) as excinfo:
        make_sync_transport(handler, max_retries=0).execute(thing_operation())

    assert excinfo.value.correlation_id == sent_requests[0].headers["X-Correlation-ID"]
    assert excinfo.value.correlation_id is not None
    assert excinfo.value.correlation_id in str(excinfo.value)


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


def test_redirects_are_not_followed_even_through_a_redirecting_client(
    config: ClientConfig,
) -> None:
    """The key must never travel to a redirect target, whatever the injected client allows."""
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/v1/things/1":
            return httpx.Response(
                302, headers={"Location": "https://elsewhere.example.test/things/1"}
            )
        return httpx.Response(200, json=thing_payload())

    http_client = httpx.Client(follow_redirects=True, transport=httpx.MockTransport(handler))
    try:
        transport = SyncTransport(config, http_client=http_client)
        with pytest.raises(UnexpectedResponseError, match=r"elsewhere\.example\.test") as excinfo:
            transport.execute(thing_operation())
    finally:
        http_client.close()

    assert excinfo.value.status_code == 302
    assert paths == ["/api/v1/things/1"]


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
) -> None:
    operation: Operation[StrictThing] = Operation(
        method="GET", path="/things/1", parse=StrictThing.model_validate
    )

    with pytest.raises(UnexpectedResponseError, match="did not match") as excinfo:
        make_sync_transport(json_response(200, {"identifier": "1", "surprise": True})).execute(
            operation
        )

    assert excinfo.value.__cause__ is not None


def test_error_status_raises_the_mapped_exception(
    make_sync_transport: Callable[..., SyncTransport],
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
) -> None:
    class ThingNotFoundError(NotFoundError):
        pass

    product = dataclasses.replace(
        EXAMPLE_PRODUCT, error_overrides={"thing_not_found": ThingNotFoundError}
    )
    custom = build_client_config(product, api_key="ex_test_key", environ={})
    handler = json_response(404, {"error": "thing_not_found", "message": "No such thing."})

    with pytest.raises(ThingNotFoundError):
        make_sync_transport(handler, transport_config=custom).execute(thing_operation())


def test_operation_status_overrides_are_applied(
    make_sync_transport: Callable[..., SyncTransport],
) -> None:
    class ThingNotFoundError(NotFoundError):
        pass

    operation: Operation[Thing] = Operation(
        method="GET",
        path="/things/1",
        parse=Thing.model_validate,
        status_overrides={404: ThingNotFoundError},
    )
    handler = json_response(404, {"error": "not_found", "message": "No such thing."})

    with pytest.raises(ThingNotFoundError):
        make_sync_transport(handler).execute(operation)


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
    status_code: int,
    payload: dict[str, Any],
    headers: dict[str, str],
    expected: type[Exception],
) -> None:
    transport = make_sync_transport(
        json_response(status_code, payload, headers=headers), max_retries=0
    )

    with pytest.raises(expected):
        transport.execute(thing_operation())


def test_quota_error_refreshes_the_balance_without_counting_a_call(
    make_sync_transport: Callable[..., SyncTransport],
) -> None:
    handler = json_response(
        429,
        {
            "error": "insufficient_quota",
            "message": "Not enough units left.",
            "usage": {"query_cost": 8, "used": 995, "limit": 1000, "remaining": 5},
        },
    )
    transport = make_sync_transport(handler)

    with pytest.raises(QuotaExceededError):
        transport.execute(thing_operation())

    assert transport.usage.last is not None
    assert transport.usage.last.remaining == 5
    assert transport.usage.spent == 0
    assert transport.usage.calls == 0


# --- transport failures -----------------------------------------------------


def test_connection_failure_is_wrapped(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    with pytest.raises(APIConnectionError, match=r"api\.example\.test \(ConnectError\)") as excinfo:
        make_sync_transport(handler, max_retries=0).execute(thing_operation())

    assert isinstance(excinfo.value.__cause__, httpx.ConnectError)
    assert excinfo.value.retryable is True
    assert excinfo.value.correlation_id == sent_requests[0].headers["X-Correlation-ID"]
    assert f"[correlation_id={excinfo.value.correlation_id}]" in str(excinfo.value)
    assert "ex_test_key" not in str(excinfo.value)


def test_read_timeout_is_wrapped_and_warns_about_billing(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    with pytest.raises(APITimeoutError, match="150 seconds") as excinfo:
        make_sync_transport(handler).execute(thing_operation())

    assert "billed" in str(excinfo.value)
    assert excinfo.value.retryable is False
    assert excinfo.value.correlation_id == sent_requests[0].headers["X-Correlation-ID"]
    assert isinstance(excinfo.value, APIConnectionError)


def test_unreadable_response_is_wrapped_and_not_retried(
    make_sync_transport: Callable[..., SyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    """A corrupt body is not a transport failure to httpx, but the API may have billed the call."""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.DecodingError("corrupt gzip")

    with pytest.raises(APIConnectionError, match="could not be read") as excinfo:
        make_sync_transport(handler).execute(thing_operation())

    assert isinstance(excinfo.value.__cause__, httpx.DecodingError)
    assert excinfo.value.retryable is False
    assert "may have been processed and billed" in str(excinfo.value)
    assert len(sent_requests) == 1


def test_malformed_request_means_nothing_was_sent(config: ClientConfig) -> None:
    prepared = prepare_request(config, thing_operation())

    error = translate_transport_error(config, prepared, httpx.LocalProtocolError("bad header"))

    assert type(error) is APIConnectionError
    assert error.retryable is False
    assert "Nothing was sent" in str(error)
    assert "billed" not in str(error)


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectTimeout("slow"),
        httpx.PoolTimeout("busy"),
        httpx.WriteTimeout("slow"),
        httpx.WriteError("closed"),
        httpx.ProxyError("refused"),
    ],
)
def test_failures_before_the_request_is_sent_are_retryable(
    config: ClientConfig, exc: httpx.TransportError
) -> None:
    error = translate_transport_error(config, prepare_request(config, thing_operation()), exc)

    assert type(error) is APIConnectionError
    assert error.retryable is True
    assert "was not sent" in str(error)
    assert type(exc).__name__ in str(error)


@pytest.mark.parametrize(
    "exc",
    [httpx.ReadError("dropped"), httpx.RemoteProtocolError("closed"), httpx.CloseError("late")],
)
def test_failures_while_reading_the_response_are_not_retryable(
    config: ClientConfig, exc: httpx.TransportError
) -> None:
    error = translate_transport_error(config, prepare_request(config, thing_operation()), exc)

    assert type(error) is APIConnectionError
    assert error.retryable is False
    assert "may have been processed and billed" in str(error)


# --- lifecycle --------------------------------------------------------------


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
        transport.execute(status_operation())


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


# --- async ------------------------------------------------------------------


async def test_async_transport_parses_a_successful_response(
    make_async_transport: Callable[..., AsyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    async with make_async_transport(json_response(200, {"status": "healthy"})) as transport:
        status = await transport.execute(status_operation())

    assert status.status == "healthy"
    assert status.request_info is not None
    assert status.request_info.path == "/status"
    assert str(sent_requests[0].url) == "https://api.example.test/status"


async def test_async_transport_raises_mapped_errors(
    make_async_transport: Callable[..., AsyncTransport],
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

    async with make_async_transport(handler, max_retries=0) as transport:
        with pytest.raises(APIConnectionError):
            await transport.execute(thing_operation())


async def test_async_budget_guard_refuses_before_sending(
    make_async_transport: Callable[..., AsyncTransport],
    sent_requests: list[httpx.Request],
) -> None:
    capped = build_client_config(
        EXAMPLE_PRODUCT, api_key="ex_test_key", max_units_per_request=1, environ={}
    )

    async with make_async_transport(json_response(200, {}), transport_config=capped) as transport:
        with pytest.raises(BudgetExceededError):
            await transport.execute(costly_operation(2))

    assert sent_requests == []


async def test_async_close_leaves_an_injected_client_open(config: ClientConfig) -> None:
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _request: httpx.Response(200))
    )

    transport = AsyncTransport(config, http_client=http_client)
    await transport.aclose()

    assert http_client.is_closed is False
    await http_client.aclose()
