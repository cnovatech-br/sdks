"""Response models shared by every Cnovatech SDK.

Product SDKs subclass :class:`APIResponse` once per endpoint and re-export the
models defined here, so their users never import this package directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ConfigDict, PrivateAttr

if TYPE_CHECKING:
    from collections.abc import Callable


@dataclass(frozen=True, slots=True)
class RequestInfo:
    """How a response was obtained.

    Attributes:
        method: HTTP method of the request.
        path: Request path, without the query string.
        status_code: HTTP status of the final response.
        correlation_id: Identifier of the request. Quote it in support requests.
        attempts: Attempts made, including the one that produced the response.
        elapsed_seconds: Wall-clock time from the first attempt to the final response.
    """

    method: str
    path: str
    status_code: int
    correlation_id: str
    attempts: int
    elapsed_seconds: float


class APIResponse(BaseModel):
    """Base class of every model built from an API response.

    Instances are immutable. Fields the API adds in the future are kept in
    ``model_extra`` instead of failing validation, so a newer API never breaks
    an older SDK.
    """

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)

    _request_info: RequestInfo | None = PrivateAttr(default=None)

    @property
    def request_info(self) -> RequestInfo | None:
        """Transport details of the request that produced this response.

        ``None`` when the model was built from data rather than by a transport,
        as happens in tests.
        """
        return self._request_info

    def attach_request_info(self, info: RequestInfo) -> None:
        """Record the transport details. Called once, by the transport that parsed the response."""
        self._request_info = info


class Usage(BaseModel):
    """Quota accounting returned with every billed response.

    ``used``, ``limit`` and ``remaining`` are ``None`` on plans without a
    monthly ceiling.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    query_cost: int
    used: int | None = None
    limit: int | None = None
    remaining: int | None = None


ModelT = TypeVar("ModelT", bound=BaseModel)


def parser_for(model: type[ModelT]) -> Callable[[Any], ModelT]:
    """Return a callable that validates a decoded JSON payload into ``model``."""
    return model.model_validate
