"""Call every endpoint of the Data Market API through the SDK and record the responses.

Two purposes: prove that every model parses what production really returns,
and refresh the test fixtures with real, anonymised data. The smallest
possible requests are used; the run costs about 21 quota units and prints the
exact figure at the end.

Usage, from the workspace root with ``DATAMARKET_API_KEY`` in the environment
or in ``.env``::

    make capture
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import httpx

from cnovatech.datamarket import DataMarket, errors

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "datamarket-python" / "tests" / "fixtures"
UNKNOWN_EAN = "0000000000000"
SAMPLE_SEARCH = "coca cola 2l"

OPERATION_IDS = {
    "/health": "healthCheck",
    "/api/v1/user/profile": "getProfile",
    "/api/v1/user/usage": "getUsage",
    "/api/v1/user/logs": "getUserLogs",
    "/api/v1/user/api-keys": "listApiKeys",
    "/api/v1/market/products/departments": "listDepartments",
    "/api/v1/market/products/brands": "listBrands",
    "/api/v1/market/products/catalog": "getCatalog",
    "/api/v1/market/products/by-brand": "getProductsByBrand",
    "/api/v1/market/products/coverage": "checkCatalogCoverage",
    "/api/v1/market/stores": "listStores",
}

ANONYMISED_PROFILE = {
    "id": "a3b1c2d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
    "email": "analyst@example.test",
    "name": "Analyst Example",
    "company_name": "Example Retail Ltda",
    "company_document": "12.345.678/0001-90",
    "phone": None,
}


class Recorder:
    """Keeps the raw JSON of every response the client received, keyed by request path."""

    def __init__(self) -> None:
        self.responses: list[tuple[str, int, Any]] = []

    def __call__(self, response: httpx.Response) -> None:
        response.read()
        try:
            payload = response.json()
        except ValueError:
            payload = None
        self.responses.append((response.request.url.path, response.status_code, payload))


def operation_id(path: str, status_code: int, payload: Any) -> str | None:
    """Name of the fixture for a recorded response, or ``None`` when it is not kept."""
    if status_code >= 400:
        code = payload.get("error") if isinstance(payload, dict) else None
        return f"error_{code}" if code in {"ean_not_found", "filter_required"} else None
    if path in OPERATION_IDS:
        return OPERATION_IDS[path]
    if "/price-history" in path:
        return "getProductPriceHistory"
    if "/products/ean/" in path:
        return "getProductByEan"
    if "/brands/" in path and path.endswith("/stores"):
        return "getStoresByBrand"
    for suffix, name in (
        ("/assortment", "getStoreAssortment"),
        ("/competitiveness", "getStoreCompetitiveness"),
        ("/products", "getCompetitorProducts"),
        ("/competitors", "getStoreCompetitors"),
        ("/market-position", "getStoreMarketPosition"),
        ("/opportunities", "getStoreOpportunities"),
    ):
        if path.endswith(suffix):
            return name
    return None


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

    try:
        client.products.get(UNKNOWN_EAN)
    except errors.EANNotFoundError:
        pass
    try:
        client.products.catalog(page=21)
    except errors.FilterRequiredError:
        pass


def main() -> int:
    """Run the capture and write the fixtures. Returns the process exit status."""
    recorder = Recorder()
    http_client = httpx.Client(event_hooks={"response": [recorder]})
    try:
        with DataMarket(http_client=http_client) as client:
            exercise(client)
            spent = client.usage.spent
    except errors.ConfigurationError as exc:
        print(f"Cannot run: {exc}", file=sys.stderr)
        return 2
    finally:
        http_client.close()

    written: list[str] = []
    for path, status_code, payload in recorder.responses:
        name = operation_id(path, status_code, payload)
        if name is None or payload is None:
            continue
        target = FIXTURES_DIR / f"{name}.json"
        target.write_text(
            json.dumps(anonymise(name, payload), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        written.append(name)

    print(f"{len(written)} fixtures written to {FIXTURES_DIR}")
    for name in sorted(written):
        print(f"  {name}.json")
    print(f"Quota spent in this run: {spent} units")
    return 0


if __name__ == "__main__":
    sys.exit(main())
