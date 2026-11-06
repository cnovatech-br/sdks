"""Models shared by every resource: base classes, the quota block, envelopes and health."""

from __future__ import annotations

from cnovatech.sdk_core.dataframe import TabularResponse
from cnovatech.sdk_core.models import (
    APIResponse,
    ListMeta,
    PaginationMeta,
    Record,
    RequestInfo,
    Usage,
)
from cnovatech.sdk_core.usage import RateLimitState

__all__ = [
    "APIResponse",
    "Health",
    "ListMeta",
    "PaginationMeta",
    "RateLimitState",
    "Record",
    "RequestInfo",
    "StoreRef",
    "TabularResponse",
    "Usage",
]


class StoreRef(Record):
    """A store's identity, as named in envelopes and extended by the store models."""

    store_id: str
    store_name: str
    city: str | None = None
    state: str | None = None
    channel: str | None = None


class Health(APIResponse):
    """Result of ``GET /health``: the API, its database and its cache.

    Only ``status`` is required: the endpoint has no published schema, and a
    monitoring probe must not fail because a detail was added or removed.
    """

    status: str
    database: str | None = None
    cache: str | None = None
    timestamp: str | None = None
    version: str | None = None

    @property
    def healthy(self) -> bool:
        """Whether the API reported itself as healthy."""
        return self.status == "healthy"
