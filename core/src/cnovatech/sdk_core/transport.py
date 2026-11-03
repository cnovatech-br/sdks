"""HTTP transports shared by the synchronous and asynchronous clients.

Preparing a request, deciding on a retry and interpreting a response are pure
functions, so both transports share one implementation and differ only in the
I/O call and in how they wait.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

import httpx
import pydantic

from .config import API_KEY_ENV_SUFFIX, ClientConfig
from .errors import (
    CORRELATION_ID_HEADER,
    APIConnectionError,
    APITimeoutError,
    BudgetExceededError,
    ConfigurationError,
    UnexpectedResponseError,
    error_from_response,
)
from .models import APIResponse, RequestInfo
from .retry import RetryDecision, RetryPolicy
from .usage import RateLimitState, UsageTracker, record_usage

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from types import TracebackType

    from typing_extensions import Self

    from .operation import Operation

logger = logging.getLogger(__name__)

ResultT = TypeVar("ResultT")

JSON_MEDIA_TYPE = "application/json"
CONTENT_TYPE_HEADER = "Content-Type"

# Failures that happen before the request reaches the API. Repeating them
# cannot bill twice. Anything else, such as a connection dropped while the
# response was being read, may already have been processed.
_SAFE_TO_REPEAT_TRANSPORT_ERRORS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.PoolTimeout,
    httpx.WriteError,
    httpx.WriteTimeout,
    httpx.ProxyError,
)


@dataclass(frozen=True, slots=True)
class PreparedRequest:
    """Everything the HTTP layer needs to send one operation."""

    method: str
    url: str
    path: str
    params: dict[str, Any]
    headers: dict[str, str]
    json_body: Any
    correlation_id: str


def prepare_request(config: ClientConfig, operation: Operation[Any]) -> PreparedRequest:
    """Build the request for ``operation``.

    ``None`` query parameters are dropped rather than serialised: the API
    treats an absent filter differently from an empty one.

    Raises:
        ConfigurationError: The operation needs an API key and none is configured.
        BudgetExceededError: The estimated cost is above ``max_units_per_request``.
    """
    api_key = config.api_key
    if operation.requires_auth and api_key is None:
        raise ConfigurationError(
            "No API key configured. Pass api_key= to the client or set the "
            f"{config.product.env_prefix}{API_KEY_ENV_SUFFIX} environment variable."
        )
    prefix = config.product.api_prefix if operation.under_api_prefix else ""
    path = f"{prefix}{operation.path}"
    budget = config.max_units_per_request
    if budget is not None and operation.estimated_cost > budget:
        raise BudgetExceededError(
            f"{operation.method} {path} is estimated at {operation.estimated_cost} quota units, "
            f"above max_units_per_request={budget}. Nothing was sent.",
            estimated_cost=operation.estimated_cost,
            limit=budget,
        )
    correlation_id = str(uuid.uuid4())
    headers = {
        "Accept": JSON_MEDIA_TYPE,
        "User-Agent": config.user_agent,
        CORRELATION_ID_HEADER: correlation_id,
    }
    if operation.requires_auth and api_key is not None:
        headers[config.product.api_key_header] = api_key.get_secret_value()
    return PreparedRequest(
        method=operation.method,
        url=f"{config.base_url}{path}",
        path=path,
        params={name: value for name, value in operation.params.items() if value is not None},
        headers=headers,
        json_body=operation.json_body,
        correlation_id=correlation_id,
    )


def interpret_response(
    config: ClientConfig,
    operation: Operation[ResultT],
    response: httpx.Response,
    *,
    prepared: PreparedRequest,
    attempts: int,
    elapsed_seconds: float,
) -> ResultT:
    """Turn the HTTP response into the operation's result, or raise the matching error.

    Raises:
        APIStatusError: The API answered with an error status.
        UnexpectedResponseError: The body is not JSON or does not match the model.
    """
    correlation_id = response.headers.get(CORRELATION_ID_HEADER) or prepared.correlation_id
    if response.status_code >= httpx.codes.BAD_REQUEST:
        raise error_from_response(
            response,
            overrides=config.product.error_overrides,
            status_overrides=operation.status_overrides,
            fallback_correlation_id=prepared.correlation_id,
        )
    payload = _decode_json(response, correlation_id=correlation_id)
    try:
        result = operation.parse(payload)
    except pydantic.ValidationError as exc:
        raise UnexpectedResponseError(
            f"The response of {prepared.method} {prepared.path} did not match the expected "
            f"shape: {exc.error_count()} validation error(s).",
            status_code=response.status_code,
            content_type=response.headers.get(CONTENT_TYPE_HEADER),
            correlation_id=correlation_id,
        ) from exc
    if isinstance(result, APIResponse):
        result.attach_request_info(
            RequestInfo(
                method=prepared.method,
                path=prepared.path,
                status_code=response.status_code,
                correlation_id=correlation_id,
                attempts=attempts,
                elapsed_seconds=elapsed_seconds,
            )
        )
    return result


def translate_transport_error(
    config: ClientConfig, prepared: PreparedRequest, exc: httpx.TransportError
) -> APIConnectionError:
    """Map an httpx transport failure to the SDK's exception, deciding whether it may be repeated."""
    if isinstance(exc, httpx.ReadTimeout):
        return APITimeoutError(
            f"The API did not answer {prepared.method} {prepared.path} within "
            f"{config.read_timeout_seconds:g} seconds. The request may still have been processed "
            "and billed, so the SDK does not retry it; check your usage before sending it again."
        )
    if isinstance(exc, _SAFE_TO_REPEAT_TRANSPORT_ERRORS):
        return APIConnectionError(
            f"Could not reach {config.hostname} ({type(exc).__name__}). The request was not sent.",
            retryable=True,
        )
    return APIConnectionError(
        f"The connection to {config.hostname} failed while {prepared.method} {prepared.path} "
        f"was in flight ({type(exc).__name__}). The request may have been processed and billed, "
        "so the SDK does not retry it.",
        retryable=False,
    )


def _decode_json(response: httpx.Response, *, correlation_id: str) -> Any:
    content_type = response.headers.get(CONTENT_TYPE_HEADER)
    media_type = (content_type or "").split(";", 1)[0].strip().lower()
    if media_type != JSON_MEDIA_TYPE:
        raise UnexpectedResponseError(
            f"Expected a JSON response but received {content_type or 'no content type'} "
            f"(HTTP {response.status_code}). Check base_url: paths the API does not know "
            "are answered by the web application.",
            status_code=response.status_code,
            content_type=content_type,
            correlation_id=correlation_id,
        )
    try:
        return response.json()
    except ValueError as exc:
        raise UnexpectedResponseError(
            f"The response body is not valid JSON (HTTP {response.status_code}).",
            status_code=response.status_code,
            content_type=content_type,
            correlation_id=correlation_id,
        ) from exc


def _log_exchange(
    prepared: PreparedRequest, response: httpx.Response, elapsed: float, attempts: int
) -> None:
    logger.debug(
        "%s %s -> %d in %.3fs after %d attempt(s)",
        prepared.method,
        prepared.path,
        response.status_code,
        elapsed,
        attempts,
        extra={
            "correlation_id": prepared.correlation_id,
            "path": prepared.path,
            "status_code": response.status_code,
            "attempts": attempts,
        },
    )


def _log_retry(
    prepared: PreparedRequest, decision: RetryDecision, attempt: int, max_attempts: int
) -> None:
    logger.info(
        "Retrying %s %s after %s: attempt %d of %d in %.2fs",
        prepared.method,
        prepared.path,
        decision.reason,
        attempt + 1,
        max_attempts,
        decision.delay_seconds,
        extra={
            "correlation_id": prepared.correlation_id,
            "path": prepared.path,
            "attempt": attempt + 1,
            "reason": decision.reason,
        },
    )


class SyncTransport:
    """Execute operations over a blocking httpx client.

    Args:
        config: Validated client settings.
        http_client: A client supplied by the user, for proxies, certificates or
            a shared pool. It is not closed by the transport.
        transport: An httpx transport for the client the transport creates
            itself. Mutually exclusive with ``http_client``.
        retry_policy: Replaces the policy built from ``config.max_retries``.
        sleep: How to wait between attempts. Tests inject a recorder.
    """

    def __init__(
        self,
        config: ClientConfig,
        *,
        http_client: httpx.Client | None = None,
        transport: httpx.BaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if http_client is not None and transport is not None:
            raise ConfigurationError("Pass either http_client or transport, not both.")
        self._config = config
        self._policy = retry_policy if retry_policy is not None else RetryPolicy(config.max_retries)
        self._sleep = sleep
        self._owns_http_client = http_client is None
        self._http_client = (
            http_client
            if http_client is not None
            else httpx.Client(timeout=config.timeout, transport=transport, follow_redirects=False)
        )
        self.usage = UsageTracker()
        self.rate_limit = RateLimitState()

    @property
    def config(self) -> ClientConfig:
        """The settings this transport was built with."""
        return self._config

    def execute(self, operation: Operation[ResultT]) -> ResultT:
        """Send ``operation``, repeating it where safe, and return its parsed result."""
        prepared = prepare_request(self._config, operation)
        started = time.perf_counter()
        attempt = 0
        while True:
            attempt += 1
            try:
                response = self._send(prepared)
            except APIConnectionError as exc:
                decision = self._policy.after_exception(exc, attempt)
                if decision is None:
                    raise
            else:
                self.rate_limit.update_from_headers(response.headers)
                decision = self._policy.after_response(response, attempt)
                if decision is None:
                    elapsed = time.perf_counter() - started
                    _log_exchange(prepared, response, elapsed, attempt)
                    result = interpret_response(
                        self._config,
                        operation,
                        response,
                        prepared=prepared,
                        attempts=attempt,
                        elapsed_seconds=elapsed,
                    )
                    record_usage(self.usage, result)
                    return result
            _log_retry(prepared, decision, attempt, self._policy.max_attempts)
            self._sleep(decision.delay_seconds)

    def _send(self, prepared: PreparedRequest) -> httpx.Response:
        try:
            return self._http_client.request(
                prepared.method,
                prepared.url,
                params=prepared.params,
                headers=prepared.headers,
                json=prepared.json_body,
                timeout=self._config.timeout,
            )
        except httpx.TransportError as exc:
            raise translate_transport_error(self._config, prepared, exc) from exc

    def close(self) -> None:
        """Close the HTTP client, unless it was supplied by the user."""
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AsyncTransport:
    """Execute operations over an asynchronous httpx client.

    Same contract as :class:`SyncTransport`; every I/O method is a coroutine
    and ``sleep`` is awaited.
    """

    def __init__(
        self,
        config: ClientConfig,
        *,
        http_client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_policy: RetryPolicy | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if http_client is not None and transport is not None:
            raise ConfigurationError("Pass either http_client or transport, not both.")
        self._config = config
        self._policy = retry_policy if retry_policy is not None else RetryPolicy(config.max_retries)
        self._sleep = sleep
        self._owns_http_client = http_client is None
        self._http_client = (
            http_client
            if http_client is not None
            else httpx.AsyncClient(
                timeout=config.timeout, transport=transport, follow_redirects=False
            )
        )
        self.usage = UsageTracker()
        self.rate_limit = RateLimitState()

    @property
    def config(self) -> ClientConfig:
        """The settings this transport was built with."""
        return self._config

    async def execute(self, operation: Operation[ResultT]) -> ResultT:
        """Send ``operation``, repeating it where safe, and return its parsed result."""
        prepared = prepare_request(self._config, operation)
        started = time.perf_counter()
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._send(prepared)
            except APIConnectionError as exc:
                decision = self._policy.after_exception(exc, attempt)
                if decision is None:
                    raise
            else:
                self.rate_limit.update_from_headers(response.headers)
                decision = self._policy.after_response(response, attempt)
                if decision is None:
                    elapsed = time.perf_counter() - started
                    _log_exchange(prepared, response, elapsed, attempt)
                    result = interpret_response(
                        self._config,
                        operation,
                        response,
                        prepared=prepared,
                        attempts=attempt,
                        elapsed_seconds=elapsed,
                    )
                    record_usage(self.usage, result)
                    return result
            _log_retry(prepared, decision, attempt, self._policy.max_attempts)
            await self._sleep(decision.delay_seconds)

    async def _send(self, prepared: PreparedRequest) -> httpx.Response:
        try:
            return await self._http_client.request(
                prepared.method,
                prepared.url,
                params=prepared.params,
                headers=prepared.headers,
                json=prepared.json_body,
                timeout=self._config.timeout,
            )
        except httpx.TransportError as exc:
            raise translate_transport_error(self._config, prepared, exc) from exc

    async def aclose(self) -> None:
        """Close the HTTP client, unless it was supplied by the user."""
        if self._owns_http_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
