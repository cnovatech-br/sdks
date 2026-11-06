# Changelog

All notable changes to `cnovatech-datamarket` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `DataMarket` and `AsyncDataMarket` clients with configuration from arguments
  or `DATAMARKET_API_KEY` / `DATAMARKET_BASE_URL`, connection pooling, context
  manager support and a `repr` that masks the key. `max_retries` and
  `max_units_per_request` are enforced by the shared core.
- `health()` on both clients: unauthenticated, free of quota cost.
- Resources covering every read endpoint of the API: `products` (`catalog`,
  `departments`, `brands`, `by_brand`, `get`, `price_history`, `coverage`),
  `stores` (`list`, `find`, `assortment`, `competitors`, `competitiveness`,
  `compare`, `market_position`, `opportunities`), `brands.stores` and
  `account` (`profile`, `usage`, `logs`, `api_keys`). Each method states its
  quota cost and estimates it before sending.
- Paginated responses (`CatalogPage`, `AssortmentPage`, ...) with
  `next_page()`, `iter_pages()` and `iter_all()` capped by `max_pages` or
  `max_units`, plus `estimate_remaining_cost()`.
- `stores.find(name)`: reads up to five pages of results until an exact name
  matches; `StoreNotFoundError` and `AmbiguousStoreError` with the
  candidates otherwise.
- `to_dataframe()` on every list response, with the `pandas` extra.
- `client.usage` (units spent through the client, last balance) and
  `client.rate_limit` (per-minute limit from the API's headers).
- `cnovatech.datamarket.errors` with `DataMarketError` as the root of every
  exception the SDK raises, plus `EANNotFoundError`, `StoreNotFoundError`,
  `FilterRequiredError`, `AmbiguousStoreError` and `BudgetExceededError`.
- `cnovatech.datamarket.models`, one module per resource, and
  `cnovatech.datamarket.types` with the input enumerations.
- `__version__`, read from the installed package metadata.
- Guides under `docs/`: quota and costs, pagination, errors and recipes.
