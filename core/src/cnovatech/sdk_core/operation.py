"""Description of one API call, independent of how it is sent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from .errors import APIStatusError

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
        status_overrides: Exception classes to raise for specific HTTP statuses
            of this call, such as a 404 on a route that names an entity.
    """

    method: Literal["GET", "POST"]
    path: str
    parse: Callable[[Any], ResultT]
    params: Mapping[str, Any] = field(default_factory=dict)
    json_body: Any = None
    estimated_cost: int = 0
    requires_auth: bool = True
    under_api_prefix: bool = True
    status_overrides: Mapping[int, type[APIStatusError]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Endpoint:
    """Where an endpoint lives, declared once and shared by every call to it.

    Attributes:
        method: HTTP method.
        path: Path template, with ``{name}`` placeholders for path parameters.
        under_api_prefix: Whether the path sits under the product's API prefix.
        requires_auth: Whether the API key must be sent.
    """

    method: Literal["GET", "POST"]
    path: str
    under_api_prefix: bool = True
    requires_auth: bool = True

    def full_path(self, api_prefix: str) -> str:
        """The path as the API serves it, with the prefix when it applies."""
        return f"{api_prefix}{self.path}" if self.under_api_prefix else self.path

    def operation(
        self,
        parse: Callable[[Any], ResultT],
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
        estimated_cost: int = 0,
        status_overrides: Mapping[int, type[APIStatusError]] | None = None,
        **path_params: str,
    ) -> Operation[ResultT]:
        """Build one call to this endpoint.

        ``path_params`` fill the template's placeholders and must already be
        validated and safe for a URL path.
        """
        return Operation(
            method=self.method,
            path=self.path.format(**path_params) if path_params else self.path,
            parse=parse,
            params=params if params is not None else {},
            json_body=json_body,
            estimated_cost=estimated_cost,
            requires_auth=self.requires_auth,
            under_api_prefix=self.under_api_prefix,
            status_overrides=status_overrides if status_overrides is not None else {},
        )
