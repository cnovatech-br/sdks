"""Helpers and fixtures for the Data Market SDK test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from cnovatech.datamarket import AsyncDataMarket, DataMarket

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ENVIRONMENT_VARIABLES = ("DATAMARKET_API_KEY", "DATAMARKET_BASE_URL")
TEST_API_KEY = "dm_test_key"
STORES_PATH = "/api/v1/market/stores"


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run the tests marked 'live' against the real API. Only free endpoints are used.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="needs --live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(autouse=True)
def _isolated_environment(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's own DATAMARKET_* variables out of the offline tests."""
    if request.config.getoption("--live"):
        return
    for name in ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def load_fixture(name: str) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return payload


def stores_page(*names: str, page: int = 1, pages: int = 1) -> dict[str, Any]:
    """A store listing page with the given names, for the lookup-by-name tests."""
    return {
        "data": [
            {
                "store_id": f"{page:04x}{index:04x}-0000-4000-8000-000000000000",
                "store_name": name,
                "state": "SP",
            }
            for index, name in enumerate(names)
        ],
        "meta": {"page": page, "limit": 100, "total": 100 * pages, "pages": pages},
        "usage": {"query_cost": 1},
    }


@pytest.fixture
def health_payload() -> dict[str, Any]:
    return load_fixture("healthCheck.json")


class FakeAPI:
    """Answers requests from fixtures and records what the client sent.

    A route matches on method, path and, when given, a subset of the query
    parameters, so one test can serve several pages of the same listing.
    """

    def __init__(self) -> None:
        self._routes: list[tuple[str, str, dict[str, str], httpx.Response]] = []
        self.requests: list[httpx.Request] = []

    def respond(
        self,
        method: str,
        path: str,
        fixture: str | dict[str, Any],
        *,
        params: dict[str, str] | None = None,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        payload = load_fixture(fixture) if isinstance(fixture, str) else fixture
        response = httpx.Response(status_code, json=payload, headers=headers)
        self._routes.append((method, path, params or {}, response))

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        query = dict(request.url.params)
        for method, path, params, response in self._routes:
            if method != request.method or path != request.url.path:
                continue
            if all(query.get(name) == value for name, value in params.items()):
                return response
        return httpx.Response(
            404,
            json={
                "error": "not_found",
                "message": f"The fake API has no route for {request.method} {request.url.path}.",
            },
        )

    @property
    def last_request(self) -> httpx.Request:
        return self.requests[-1]

    @property
    def last_params(self) -> dict[str, str]:
        return dict(self.last_request.url.params)

    def client(self, *, api_key: str | None = TEST_API_KEY, **options: Any) -> DataMarket:
        return DataMarket(api_key=api_key, transport=httpx.MockTransport(self.handler), **options)

    def async_client(
        self, *, api_key: str | None = TEST_API_KEY, **options: Any
    ) -> AsyncDataMarket:
        return AsyncDataMarket(
            api_key=api_key, transport=httpx.MockTransport(self.handler), **options
        )


@pytest.fixture
def api() -> FakeAPI:
    return FakeAPI()
