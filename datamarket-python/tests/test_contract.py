"""The SDK covers every live, read-only operation of the API, and nothing the API does not have."""

from __future__ import annotations

import json

from conftest import FIXTURES_DIR

from cnovatech.datamarket._config import API_PREFIX
from cnovatech.datamarket.resources import _operations as operations

OPENAPI_DOCUMENT = FIXTURES_DIR / "openapi.json"
OUT_OF_SCOPE_PREFIXES = ("/api/v1/user/account", "/api/v1/user/change-password")


def openapi_operations() -> set[tuple[str, str]]:
    document = json.loads(OPENAPI_DOCUMENT.read_text(encoding="utf-8"))
    found: set[tuple[str, str]] = set()
    for path, item in document["paths"].items():
        if path.startswith(OUT_OF_SCOPE_PREFIXES):
            continue
        for method in ("get", "post", "put", "delete"):
            if method not in item:
                continue
            if path.startswith("/api/v1/user") and method != "get":
                continue  # account mutations are out of scope by design
            found.add((method.upper(), path))
    return found


def sdk_operations() -> set[tuple[str, str]]:
    return {(endpoint.method, endpoint.full_path(API_PREFIX)) for endpoint in operations.ENDPOINTS}


def test_every_live_operation_has_an_sdk_counterpart() -> None:
    assert sdk_operations() == openapi_operations()


def test_endpoint_count_matches_the_documented_scope() -> None:
    assert len(operations.ENDPOINTS) == 20


def test_only_the_health_check_sits_outside_the_prefix() -> None:
    outside = [endpoint for endpoint in operations.ENDPOINTS if not endpoint.under_api_prefix]

    assert outside == [operations.HEALTH]
    assert operations.HEALTH.requires_auth is False
    assert all(
        endpoint.requires_auth
        for endpoint in operations.ENDPOINTS
        if endpoint is not operations.HEALTH
    )
