# Quota and costs

Every billed call consumes quota units from the account's cycle, and every
billed response says what it cost. This guide explains the tariff, how the SDK
reports and estimates it, and how to cap what a program may spend.

## What a call costs

| Call | Units |
|---|---|
| `products.catalog`, `departments`, `brands`, `by_brand`, `get`, `price_history` | 1 per call or page |
| `products.coverage(eans)` | 1 per started block of 250 codes (500 codes: 2) |
| `stores.list`, `stores.find` | 1 per page read (`find` usually reads one) |
| `stores.competitors`, `stores.competitiveness` | 1 per competitor returned, capped by `limit` |
| `stores.assortment`, `compare`, `market_position`, `opportunities` | 2 per started block of 250 rows, per page |
| `brands.stores` | 1 |
| `account.*`, `health()` | free |

Errors are free: a 404 for an unknown EAN, a 400 for a missing filter and any
other 4xx or 5xx do not consume quota.

Two examples of the export rule: `stores.assortment(store_id, limit=100)`
costs 2 units per page; `stores.market_position(store_id, limit=1000)` costs
8 units per page. A page of 251 rows costs the same as a page of 500.

## What a call really cost

The API is the only authority on cost. Every billed response carries a
`usage` block:

```python
product = client.products.get("7894900027013")
product.usage.query_cost  # 1, units consumed by this call
product.usage.used  # units used in the cycle, including this call
product.usage.limit  # units available in the cycle
product.usage.remaining  # units left
```

On plans without a ceiling, `used`, `limit` and `remaining` are `None`.

The client accumulates what it saw:

```python
client.usage.spent  # units consumed through this client since it was created
client.usage.calls  # billed responses recorded
client.usage.last  # the most recent usage block, with the current balance
```

Two clients never share accounting.

When the remaining balance drops below 10% of the limit, the SDK logs one
warning on the `cnovatech` logger, and logs it again only after the balance
has recovered and dropped again.

## Estimates, before sending

The SDK knows the tariff and estimates each call before sending it. The
estimate is used for two things only: the per-request budget guard and the
cost of pages not fetched yet. The recorded cost is always the real one.

### Refusing an expensive call

```python
client = DataMarket(max_units_per_request=20)

client.stores.market_position(store_id, limit=1000)  # estimated at 8: sent
client.stores.competitors(store_id, limit=50)  # estimated at 50: refused
```

The refused call raises `BudgetExceededError` before anything reaches the
network. The exception carries `estimated_cost` and `limit`. The guard is off
by default.

### Pages not fetched yet

```python
page = client.stores.assortment(store_id, limit=1000)
page.page_cost_estimate  # 8
page.meta.pages  # 6
page.estimate_remaining_cost()  # 40, for the five pages after this one
```

See [Pagination](pagination.md) for `max_units`, which caps an iteration by
what it actually spends.

## Rate limit

Separately from quota, the API allows a number of requests per minute. A
request over that limit answers 429 with code `rate_limit_exceeded`, and the
SDK retries it after `Retry-After` seconds, up to `max_retries` times, before
raising `RateLimitError`. The last known state is on the client:

```python
client.rate_limit.limit  # requests allowed per minute
client.rate_limit.remaining  # requests left in the current minute
client.rate_limit.reset_in_seconds  # until the minute ends
```

The fields are `None` until a response carries the headers, and stay `None`
on accounts the API does not rate-limit.

## Running out

A 429 with any other code is a quota error and raises `QuotaExceededError`,
which the SDK never retries. The exception says which ceiling was hit in
`code` (`monthly_limit_exceeded`, `trial_quota_exceeded` or
`insufficient_quota`) and, when the API offers them, `upgrade_url`,
`early_renewal_url` and `can_renew`.

A read timeout is the one case where the SDK cannot know whether a call was
billed: the API may have processed the request after the client stopped
waiting. `APITimeoutError` says so, and the SDK does not retry it. Check
`client.account.usage()` before sending the same call again.
