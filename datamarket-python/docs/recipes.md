# Recipes

Working patterns for the questions the API answers best, with the quota each
one costs. All examples assume `client = DataMarket()` with the key in
`DATAMARKET_API_KEY`.

## How much of my list does the catalogue cover

One call checks up to 500 codes for 2 units; a list of 2,000 codes costs 8.

```python
codes = [row["ean"] for row in my_products]

covered: list[str] = []
for start in range(0, len(codes), 500):
    coverage = client.products.coverage(codes[start : start + 500])
    covered.extend(item.ean for item in coverage.data if item.found)
    print(f"{coverage.summary.coverage_pct:.1f}% of this block is in the catalogue")
```

Codes that are not valid EANs are counted in `summary.invalid_count` rather
than rejected, so the list can go in as it is.

## My store against its competitors

```python
store = client.stores.find("Supermercado Modelo", state="SP")  # 1 unit

competitors = client.stores.competitors(store.store_id, limit=5)  # 5 units
score = client.stores.competitiveness(store.store_id, limit=5)  # 5 units
print(score.summary.competitiveness_score)

rival = competitors.data[0]
comparison = client.stores.compare(store.store_id, rival.store_id, price_position="above")
for item in comparison.iter_all(max_units=20):  # 2 units per page of 50
    print(item.product_name, item.price, item.competitor_price, item.price_diff_pct)
```

`limit` caps both the result and the cost of the two analyses.

## The whole assortment against the market, as a table

```python
position = client.stores.market_position(store.store_id, limit=1000)  # 8 units per page
print(position.meta.pages, "pages,", position.estimate_remaining_cost(), "units to finish")

frames = [page.to_dataframe() for page in position.iter_pages(max_units=80)]
table = pandas.concat(frames, ignore_index=True)
table.to_parquet("market_position.parquet")
```

The DataFrame has one row per product, nested statistics flattened
(`market_median_price`) and the envelope repeated on each row (`store_id`,
`summary_product_count`, `usage_query_cost`). Requires the `pandas` extra.

## When to look up one product and when to export

`products.get(ean)` answers one product with the offer of every store, for 1
unit, and the first lookup of a product the API has not cached yet can take
up to 90 seconds. It is the right call for a handful of products.

For a store's whole range, do not loop over `get`: 5,000 products would cost
5,000 units and hours. `stores.assortment` gives the store's own prices and
`stores.market_position` gives each product against the market, both at 2
units per 250 rows. The rule of thumb:

| Question | Call | Cost for 5,000 products |
|---|---|---|
| What does every store charge for this product? | `products.get` | 1 per product |
| What does my store sell, at what price? | `stores.assortment` | 40 |
| How does each of my products sit against the market? | `stores.market_position` | 40 |
| Which products should I reprice? | `stores.opportunities` | 2 per page of 50 |

## Price history of a product

```python
history = client.products.price_history("7894900027013", days=90, granularity="weekly")  # 1 unit

for bucket in history.market_series:
    print(bucket.date, bucket.median_price, bucket.store_count)

by_store = history.to_dataframe(series="stores")  # one row per store and day
```

## Many products, in parallel, without tripping the rate limit

The asynchronous client issues requests concurrently. The API allows a fixed
number of requests per minute, so bound the concurrency yourself; the SDK
retries a per-minute 429 with the wait the API asks for, but a tight loop
spends those retries fast.

```python
import asyncio

from cnovatech.datamarket import AsyncDataMarket, errors


async def main(eans: list[str]) -> None:
    gate = asyncio.Semaphore(5)
    async with AsyncDataMarket() as client:

        async def lookup(ean: str):
            async with gate:
                try:
                    return await client.products.get(ean)
                except errors.EANNotFoundError:
                    return None

        products = await asyncio.gather(*(lookup(ean) for ean in eans))
    print(client.usage.spent, "units")


asyncio.run(main(my_eans))
```

## Keeping a job within a budget

```python
client = DataMarket(max_units_per_request=10)
```

refuses, before sending, any single call estimated above 10 units. For walks
over pages, `max_units` on `iter_pages()` and `iter_all()` does the same for
the whole walk. Both raise `BudgetExceededError`; nothing is sent past the cap.

## Proxies, certificates and your own connection pool

Pass your own `httpx.Client`; the SDK uses it and never closes it:

```python
import httpx

http_client = httpx.Client(proxy="http://proxy.example:3128", verify="/etc/ssl/corp.pem")
client = DataMarket(http_client=http_client)
```

## Seeing what the SDK does

```python
import logging

logging.basicConfig(level=logging.INFO)
logging.getLogger("cnovatech").setLevel(logging.DEBUG)
```

DEBUG shows each request's method, path, status and duration; INFO shows
retries; WARNING shows the low-quota notice. The key, the headers and the
bodies are never logged. The `httpx` logger, if the application enables it at
INFO, prints the full URL with its query string; the key is not in it.
