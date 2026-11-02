"""Shared foundation of the Cnovatech Python SDKs.

This package is not used directly by application code. The product SDKs build
on it and re-export what their users need. It knows nothing about any product:
no endpoint, field name or domain concept lives here, and CI enforces that
boundary.
"""

from __future__ import annotations

from .config import ClientConfig, ProductSettings, build_client_config
from .metadata import read_distribution_version
from .models import APIResponse, Health, RequestInfo, Usage, parser_for
from .operation import Operation
from .transport import AsyncTransport, SyncTransport

__version__ = read_distribution_version("cnovatech-sdk-core")

__all__ = [
    "APIResponse",
    "AsyncTransport",
    "ClientConfig",
    "Health",
    "Operation",
    "ProductSettings",
    "RequestInfo",
    "SyncTransport",
    "Usage",
    "__version__",
    "build_client_config",
    "parser_for",
    "read_distribution_version",
]
