"""Call every endpoint of the Data Market API through the SDK and record the responses.

Two purposes: prove that every model parses what production really returns,
and refresh the test fixtures with real data, anonymised and with every list
cut to its first five items. The smallest possible requests are used; the run
costs about 21 quota units and prints the exact figure at the end.

Fixtures are named after the ``operationId`` of the matching path in the
OpenAPI document kept next to them, so a new endpoint only needs the document
refreshed.

Usage, from the workspace root with ``DATAMARKET_API_KEY`` in the environment
or in ``.env``::

    make capture
"""

from __future__ import annotations

import contextlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx

from cnovatech.datamarket import DataMarket, errors
from cnovatech.datamarket._config import PRODUCT_SETTINGS

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "datamarket-python" / "tests" / "fixtures"
OPENAPI_DOCUMENT = FIXTURES_DIR / "openapi.json"
UNKNOWN_EAN = "0000000000000"
SAMPLE_SEARCH = "coca cola 2l"
# Above the API's maximum window, so the request is refused with a 422 and not billed.
OUT_OF_RANGE_DAYS = 400

# Error bodies worth keeping: the codes the SDK types specially, plus the
# validation error, whose shape every 422 shares.
KEPT_ERROR_CODES = frozenset(PRODUCT_SETTINGS.error_overrides) | {"validation_error"}

ANONYMISED_PROFILE = {
    "id": "a3b1c2d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    "email": "analyst@example.test",
    "name": "Analyst Example",
    "company_name": "Example Retail Ltda",
    "company_document": "12.345.678/0001-90",
    "phone": None,
}

Recorded = tuple[str, str, int, Any]
"""Method, path, status and decoded body of one response."""


class Recorder:
    """Keeps the raw JSON of every response the client received."""

    def __init__(self) -> None:
        self.responses: list[Recorded] = []

    def __call__(self, response: httpx.Response) -> None:
        """Record one response. Installed as an httpx ``response`` event hook."""
        response.read()
        try:
            payload = response.json()
        except ValueError:
            payload = None
        request = response.request
        self.responses.append((request.method, request.url.path, response.status_code, payload))


def route_names() -> list[tuple[str, re.Pattern[str], str]]:
    """``(method, path pattern, operationId)`` for every operation of the OpenAPI document."""
    document = json.loads(OPENAPI_DOCUMENT.read_text(encoding="utf-8"))
    routes: list[tuple[str, re.Pattern[str], str]] = []
    for template, item in document["paths"].items():
        literals = re.split(r"\{[^/]+\}", template)
        pattern = re.compile("^" + "[^/]+".join(re.escape(piece) for piece in literals) + "$")
        for method, operation in item.items():
            if isinstance(operation, dict) and "operationId" in operation:
                routes.append((method.upper(), pattern, operation["operationId"]))
    return routes


def fixture_name(recorded: Recorded, routes: list[tuple[str, re.Pattern[str], str]]) -> str | None:
    """Name of the fixture for a recorded response, or ``None`` when it is not kept.

    Error responses are kept only for the codes in :data:`KEPT_ERROR_CODES`.
    """
    method, path, status_code, payload = recorded
    if status_code >= 400:
        code = payload.get("error") if isinstance(payload, dict) else None
        return f"error_{code}" if code in KEPT_ERROR_CODES else None
    for route_method, pattern, name in routes:
        if route_method == method and pattern.match(path):
            return name
    return None


def trim_lists(payload: Any, *, limit: int = 5) -> Any:
    """Keep at most ``limit`` items in every list, so fixtures stay small and readable.

    Counts in summaries and ``meta`` still describe the full response.
    """
    if isinstance(payload, dict):
        return {key: trim_lists(value, limit=limit) for key, value in payload.items()}
    if isinstance(payload, list):
        return [trim_lists(item, limit=limit) for item in payload[:limit]]
    return payload


def anonymise(name: str, payload: Any) -> Any:
    """Strip account identity from the fixtures that carry it."""
    if name == "getProfile" and isinstance(payload, dict):
        return {**payload, **ANONYMISED_PROFILE}
    if name == "getUserLogs" and isinstance(payload, dict):
        entries = [
            {**entry, "ip_address": "203.0.113.10", "api_key_prefix": "dm_12ab"}
            for entry in payload.get("data", [])
        ]
        return {**payload, "data": entries}
    if name == "listApiKeys" and isinstance(payload, dict):
        keys = [
            {
                **key,
                "id": f"e1f2a3b4-c5d6-4e7f-8a9b-0c1d2e3f4a5{index}",
                "key_prefix": "dm_12ab",
                "name": f"Key {index + 1}",
            }
            for index, key in enumerate(payload.get("data", []))
        ]
        return {**payload, "data": keys}
    return payload


def exercise(client: DataMarket) -> None:
    """Call every endpoint once, with the smallest requests that still return data."""
    client.health()
    client.account.profile()
    client.account.usage()
    client.account.logs(limit=5)
    client.account.api_keys()

    client.products.departments()
    brands = client.products.brands(limit=5)
    catalog = client.products.catalog(search=SAMPLE_SEARCH, limit=5)
    if not catalog.data:
        raise RuntimeError(f"The catalogue returned nothing for {SAMPLE_SEARCH!r}.")
    product = client.products.get(catalog.data[0].ean)
    client.products.price_history(product.ean, days=7, store_limit=3)
    client.products.by_brand(product.brand or brands.data[0].brand, limit=5)
    client.products.coverage([product.ean, UNKNOWN_EAN])
    client.brands.stores(product.brand or brands.data[0].brand)

    stores = client.stores.list(limit=5)
    store_id = stores.data[0].store_id
    client.stores.assortment(store_id, limit=5)
    competitors = client.stores.competitors(store_id, limit=2)
    client.stores.competitiveness(store_id, limit=2)
    if competitors.data:
        client.stores.compare(store_id, competitors.data[0].store_id, limit=5)
    client.stores.market_position(store_id, limit=5)
    client.stores.opportunities(store_id, limit=5)

    # These errors are expected and free; their bodies become the error fixtures.
    with contextlib.suppress(errors.EANNotFoundError):
        client.products.get(UNKNOWN_EAN)
    with contextlib.suppress(errors.FilterRequiredError):
        client.products.catalog(page=21)
    with contextlib.suppress(errors.UnprocessableEntityError):
        client.products.price_history(product.ean, days=OUT_OF_RANGE_DAYS)


def write_fixtures(responses: list[Recorded]) -> list[str]:
    """Write one fixture per recorded response that has a name. Returns the names written."""
    routes = route_names()
    written: list[str] = []
    for recorded in responses:
        name = fixture_name(recorded, routes)
        payload = recorded[3]
        if name is None or payload is None:
            continue
        content = trim_lists(anonymise(name, payload))
        (FIXTURES_DIR / f"{name}.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written.append(name)
    return written


def main() -> int:
    """Run the capture and write the fixtures. Returns the process exit status.

    Whatever was recorded before a failure is still written, so the quota
    already spent is not wasted on a second run.
    """
    recorder = Recorder()
    http_client = httpx.Client(event_hooks={"response": [recorder]})
    spent = 0
    status = 0
    try:
        with DataMarket(http_client=http_client) as client:
            try:
                exercise(client)
            finally:
                spent = client.usage.spent
    except errors.ConfigurationError as exc:
        print(f"Cannot run: {exc}", file=sys.stderr)
        return 2
    except (errors.DataMarketError, RuntimeError) as exc:
        print(f"Stopped early: {exc}", file=sys.stderr)
        status = 1
    finally:
        http_client.close()

    written = write_fixtures(recorder.responses)
    print(f"{len(written)} fixtures written to {FIXTURES_DIR}")
    for name in sorted(written):
        print(f"  {name}.json")
    print(f"Quota spent in this run: {spent} units")
    return status


if __name__ == "__main__":
    sys.exit(main())
