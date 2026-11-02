"""Description of one API call, independent of how it is sent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

ResultT = TypeVar("ResultT")


@dataclass(frozen=True)
class Operation(Generic[ResultT]):
    """One API call: where it goes, what it sends and how its result is parsed.

    Resources build operations; transports execute them. Keeping the two apart
    lets the synchronous and asynchronous clients share every decision except
    the I/O call itself.

    Attributes:
        method: HTTP method.
        path: Path of the endpoint. Relative to the product's API prefix unless
            ``under_api_prefix`` is false.
        parse: Turns the decoded JSON payload into the result. Usually
            ``Model.model_validate``.
        params: Query parameters. ``None`` values are omitted from the request.
        json_body: JSON body for ``POST`` calls.
        estimated_cost: Quota units the call is expected to consume, computed
            before it is sent. Zero for free endpoints.
        requires_auth: Whether the API key must be sent.
        under_api_prefix: Whether ``path`` sits under the product's API prefix.
    """

    method: Literal["GET", "POST"]
    path: str
    parse: Callable[[Any], ResultT]
    params: Mapping[str, Any] = field(default_factory=dict)
    json_body: Any = None
    estimated_cost: int = 0
    requires_auth: bool = True
    under_api_prefix: bool = True
