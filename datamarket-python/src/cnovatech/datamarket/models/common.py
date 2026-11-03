"""Models shared by every resource: base classes, the quota block, envelopes and health."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from cnovatech.sdk_core.dataframe import TabularResponse
from cnovatech.sdk_core.models import APIResponse, ListMeta, PaginationMeta, RequestInfo, Usage
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


class Record(BaseModel):
    """Base of every object nested inside a response: immutable, keeps unknown fields."""

    model_config = ConfigDict(frozen=True, extra="allow", populate_by_name=True)


class StoreRef(Record):
    """A store named in a response envelope: the one queried, or the competitor compared."""

    store_id: str
    store_name: str
    city: str | None = None
    state: str | None = None
    channel: str | None = None


class Health(APIResponse):
    """Result of ``GET /health``: the API, its database and its cache."""

    status: str
    database: str
    cache: str
    timestamp: str
    version: str

    @property
    def healthy(self) -> bool:
        """Whether the API reported itself as healthy."""
        return self.status == "healthy"
