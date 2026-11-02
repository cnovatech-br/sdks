"""Models shared by every resource: the response base class, quota usage, request details and health."""

from __future__ import annotations

from cnovatech.sdk_core.models import APIResponse, RequestInfo, Usage

__all__ = ["APIResponse", "Health", "RequestInfo", "Usage"]


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
