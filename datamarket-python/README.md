# cnovatech-datamarket

Official Python SDK for the [Cnovatech Data Market](https://datamarket.cnovatech.com.br)
API: daily prices, availability and assortment of more than 150,000 products
across 240+ online supermarkets in 23 Brazilian states.

- Synchronous and asynchronous clients with the same surface
- Every response carries its quota cost; pagination can be capped by cost
- Retries only where a repeat cannot be billed twice
- Typed end to end: pydantic models, `py.typed`, `mypy --strict`

> **Status: pre-release.** Every read endpoint of the API is implemented,
> validated against production and tested offline against recorded responses.
> The first release to PyPI is next. See the
> [changelog](https://github.com/cnovatech-br/sdks/blob/main/datamarket-python/CHANGELOG.md).

## Installation

```bash
pip install cnovatech-datamarket
```

Add `[pandas]` for `to_dataframe()` on list responses. Python 3.10 or newer.

## Quick start

```python
from cnovatech.datamarket import DataMarket

client = DataMarket()  # reads DATAMARKET_API_KEY

product = client.products.get("7894900011517", state="SP")

product.product_name  # "Refrigerante Coca-Cola 2L"
product.market.median_price  # 9.49
product.offers[0].store_name  # "Supermercado Modelo"
product.offers[0].price  # 8.99
product.offers[0].available  # True

product.usage.query_cost  # 1
product.usage.remaining  # 994
```

Get a key at <https://datamarket.cnovatech.com.br>. `client.health()` checks
the API without a key and without cost.

The first lookup of a product the API has not cached yet can take up to 90
seconds; after that it answers in under a second. The default timeout allows
for it.

## Quota

Every call is billed in quota units, and every response says what it cost:

```python
page = client.products.catalog(search="azeite", limit=50)
page.usage.query_cost  # 1
page.usage.remaining  # 993
client.usage.spent  # 2, through this client
```

Paginated responses can be walked page by page or item by item, with a ceiling
on how much to spend:

```python
position = client.stores.market_position(store_id, limit=1000)  # 8 units per page
position.meta.pages  # 4
position.estimate_remaining_cost()  # 24, for the three pages not fetched yet

items = list(position.iter_all(max_units=40))
items[0].product_name  # "Azeite Extra Virgem 500ml"
items[0].price_position  # "above"
```

`iter_all` never requests again the page you already paid for. It stops quietly
at `max_pages` and raises `BudgetExceededError` before a page that would cross
`max_units`. To refuse any single call above a budget, build the client with
`DataMarket(max_units_per_request=20)`.

## Stores and competitors

```python
store = client.stores.find("Supermercado Modelo", state="SP")  # 1 unit
store.store_id  # "0f8c7d2e-6b1a-4f3e-9c5d-2a7b8e1f4c63"

competitors = client.stores.competitors(store.store_id, limit=5)  # 1 unit each
competitors.data[0].store_name  # "Mercado Vizinho"
competitors.data[0].overlap_pct  # 62.5, share of the assortment in common

comparison = client.stores.compare(store.store_id, competitors.data[0].store_id)
comparison.data[0].product_name  # "Azeite Extra Virgem 500ml"
comparison.data[0].price_position  # "above"
comparison.data[0].price_diff_pct  # 12.3
```

## Errors

```python
from cnovatech.datamarket import DataMarket, errors

client = DataMarket()

try:
    product = client.products.get("0000000000000")
except errors.EANNotFoundError as exc:
    exc.hint  # what the API suggests doing next
except errors.QuotaExceededError as exc:
    exc.code  # "monthly_limit_exceeded"
    exc.upgrade_url  # where to change plan
except errors.APITimeoutError:
    ...  # may have been billed; check client.account.usage() before repeating
except errors.DataMarketError as exc:
    str(exc)  # "HTTP 503 service_unavailable: ... [correlation_id=...]"; never the key
```

Connection errors, 502/503 and the per-minute 429 are retried with backoff.
Read timeouts, 504 and quota errors never are: the request may already have
been processed and billed.

## Async

```python
import asyncio

from cnovatech.datamarket import AsyncDataMarket


async def main() -> None:
    async with AsyncDataMarket() as client:
        product = await client.products.get("7894900011517")
        product.market.median_price  # 9.49


asyncio.run(main())
```

## pandas

```python
assortment = client.stores.assortment(store.store_id, limit=1000)
frame = assortment.to_dataframe()  # one row per item; usage and meta as columns
```

## Configuration

| Argument | Environment variable | Default |
|---|---|---|
| `api_key` | `DATAMARKET_API_KEY` | required, except for `health()` |
| `base_url` | `DATAMARKET_BASE_URL` | `https://datamarket.cnovatech.com.br` |
| `timeout` | | 150 s read timeout; pass `httpx.Timeout` to set every phase. Applies per request, also through your own `http_client` |
| `max_retries` | | 2 |
| `max_units_per_request` | | no limit |
| `http_client` | | your own `httpx.Client`, for proxies, certificates or a shared pool; never closed, redirects never followed |

## Guides

- [Quota and costs](https://github.com/cnovatech-br/sdks/blob/main/datamarket-python/docs/quota-and-costs.md): the tariff, what each response reports, estimates and caps.
- [Pagination](https://github.com/cnovatech-br/sdks/blob/main/datamarket-python/docs/pagination.md): pages, walks, `max_pages` and `max_units`.
- [Errors](https://github.com/cnovatech-br/sdks/blob/main/datamarket-python/docs/errors.md): the hierarchy, what is retried, how to handle each case.
- [Recipes](https://github.com/cnovatech-br/sdks/blob/main/datamarket-python/docs/recipes.md): coverage of a list, competitors, exports to pandas, when to use `get` and when to export.

## Logging

The SDK logs through the standard `logging` module under the `cnovatech`
namespace and installs no handler of its own. At DEBUG it records each request's
method, path, status and duration; retries are logged at INFO, and a WARNING is
emitted when the remaining quota drops below 10%. Keys, headers and bodies are
never logged. The `httpx` logger, if the application enables it at INFO, prints
the full URL with its query string; the key is sent as a header and is not in it.

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("cnovatech").setLevel(logging.DEBUG)
```

## Resources

| Resource | Methods | Cost |
|---|---|---|
| `client.products` | `catalog`, `departments`, `brands`, `by_brand`, `get`, `price_history` | 1 unit |
| | `coverage` | ceil(codes / 250) units; up to 500 codes per call |
| `client.stores` | `list`, `find` | 1 unit |
| | `competitors`, `competitiveness` | 1 unit per competitor |
| | `assortment`, `compare`, `market_position`, `opportunities` | ceil(rows / 250) × 2 units per page |
| `client.brands` | `stores` | 1 unit |
| `client.account` | `profile`, `usage`, `logs`, `api_keys` | free |
| `client` | `health`, `usage`, `rate_limit`, `close` | free |

Each method's docstring states its cost. The API reference is at
<https://datamarket.cnovatech.com.br/redoc>.

## Support

- Issues and feature requests: <https://github.com/cnovatech-br/sdks/issues>
- Email: <suporte@cnovatech.com.br>

## License

To be defined before the first stable release. The API terms of use are at
<https://cnovatech.com.br/termos-de-uso>.
