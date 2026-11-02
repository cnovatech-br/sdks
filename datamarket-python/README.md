# cnovatech-datamarket

Official Python SDK for the [Cnovatech Data Market](https://datamarket.cnovatech.com.br)
API: price, availability and assortment intelligence for more than 150,000
products across 240+ online supermarkets in 23 Brazilian states, collected daily.

> **Pre-release.** The client, its configuration and `health()` are implemented.
> The resources listed below are the committed design and arrive in the next
> releases. Nothing here is published to PyPI yet.

## Installation

```bash
pip install cnovatech-datamarket            # httpx and pydantic, nothing else
pip install "cnovatech-datamarket[pandas]"  # adds .to_dataframe() to list responses
```

Python 3.10 or newer.

## Quick start

```python
from cnovatech.datamarket import DataMarket

client = DataMarket()  # reads DATAMARKET_API_KEY from the environment

page = client.products.catalog(search="coca cola 2l", brand="COCA-COLA")
product = client.products.get(page.data[0].ean, state="SP")

print(product.product_name, product.market.median_price)
for offer in product.offers[:5]:
    print(offer.store_name, offer.price, offer.available)

print(
    "cost:",
    page.usage.query_cost + product.usage.query_cost,
    "units;",
    "remaining:",
    product.usage.remaining,
)
```

## What the SDK guarantees

- **Visible cost.** Every response carries `.usage` (`query_cost`, `used`,
  `limit`, `remaining`) and the client accumulates `client.usage.spent`.
  Automatic pagination accepts `max_pages` and `max_units`.
- **Retries that never bill twice.** Connection errors, 502/503/504 and the
  per-minute 429 are retried (honouring `Retry-After`). Read timeouts and
  quota errors are never retried.
- **A realistic timeout.** 150 s of read timeout: the first lookup of an
  uncached product can take about 90 s on the API; afterwards it answers in
  under a second.
- **Typed errors.** `EANNotFoundError`, `QuotaExceededError`, `RateLimitError`,
  `FilterRequiredError`... each with `status_code`, `code`, `correlation_id`
  and `usage`.
- **Sync and async** with the same surface: `DataMarket` and `AsyncDataMarket`.
- **Typed end to end.** Pydantic models, `py.typed`, `mypy --strict`.
- **The key never leaks** into `repr`, logs or tracebacks.

## Resources

| Resource | Methods |
|---|---|
| `client.products` | `catalog`, `departments`, `brands`, `by_brand`, `get`, `price_history`, `coverage` |
| `client.stores` | `list`, `find`, `assortment`, `competitors`, `competitiveness`, `compare`, `market_position`, `opportunities` |
| `client.brands` | `stores` |
| `client.account` | `profile`, `usage`, `logs`, `api_keys` |
| `client` | `health`, `usage`, `rate_limit` |

## Configuration

| Setting | Constructor argument | Environment variable | Default |
|---|---|---|---|
| API key | `api_key` | `DATAMARKET_API_KEY` | none; only `health()` works without it |
| Base URL | `base_url` | `DATAMARKET_BASE_URL` | `https://datamarket.cnovatech.com.br` |
| Read timeout | `timeout` | | 150 s |
| Retries | `max_retries` | | 2 |
| Per-call budget | `max_units_per_request` | | off |

## Development

This package lives in the [Cnovatech SDKs workspace](../README.md). From the
workspace root:

```bash
make install     # workspace virtualenv with every package and the dev tools
make check       # ruff, boundary check, mypy --strict, tests with coverage
make live        # smoke test against the real API; free endpoints only
```

## License

To be defined before the first release. The Data Market API terms of use are at
<https://cnovatech.com.br/termos-de-uso>.
