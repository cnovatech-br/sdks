"""Fixtures for the Data Market SDK test suite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ENVIRONMENT_VARIABLES = ("DATAMARKET_API_KEY", "DATAMARKET_BASE_URL")


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


def load_fixture(name: str) -> Any:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture
def health_payload() -> dict[str, Any]:
    payload: dict[str, Any] = load_fixture("healthCheck.json")
    return payload
