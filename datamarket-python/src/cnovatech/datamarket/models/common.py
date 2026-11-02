"""Models shared by every resource: the response base class, quota usage and request details."""

from __future__ import annotations

from cnovatech.sdk_core.models import APIResponse, Health, RequestInfo, Usage

__all__ = ["APIResponse", "Health", "RequestInfo", "Usage"]
