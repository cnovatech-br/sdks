# Changelog

All notable changes to `cnovatech-datamarket` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `DataMarket` and `AsyncDataMarket` clients with configuration from arguments
  or `DATAMARKET_API_KEY` / `DATAMARKET_BASE_URL`, connection pooling, context
  manager support and a `repr` that masks the key. `max_retries` and
  `max_units_per_request` are enforced by the shared core. A client can be
  shared between threads; responses, pages and exceptions can be pickled.
- `health()` on both clients: unauthenticated, free of quota cost, and
  tolerant of changes in the unversioned health body.
- Resources covering every read endpoint of the API: `products` (`catalog`,
  `departments`, `brands`, `by_brand`, `get`, `price_history`, `coverage`),
  `stores` (`list`, `find`, `assortment`, `competitors`, `competitiveness`,
  `compare`, `market_position`, `opportunities`), `brands.stores` and
  `account` (`profile`, `usage`, `logs`, `api_keys`). Each method states its
  quota cost and estimates it before sending. `coverage()` takes any
  iterable of codes; store identifiers may be `uuid.UUID` objects.
- Paginated responses (`CatalogPage`, `AssortmentPage`, ...) with
  `next_page()`, `iter_pages()` and `iter_all()` capped by `max_pages` or
  `max_units`, plus `estimate_remaining_cost()`.
- `stores.find(name)`: reads up to five pages of results until an exact name
  matches; `StoreNotFoundError` and `AmbiguousStoreError` with the
  candidates otherwise. A blank name is refused before anything is sent.
- `to_dataframe()` on every list response, with the `pandas` extra. An
  envelope field that shares its name with a row field keeps its own column,
  prefixed by the response's name (`product_image_url`).
- `client.usage` (units spent through the client, last balance, refreshed
  by quota errors too) and `client.rate_limit` (per-minute limit from the
  API's headers).
- `cnovatech.datamarket.errors` with `DataMarketError` as the root of every
  exception the SDK raises, plus `EANNotFoundError`, `StoreNotFoundError`,
  `FilterRequiredError`, `AmbiguousStoreError` and `BudgetExceededError`.
  Connection errors and timeouts carry the `correlation_id` of the request.
- `cnovatech.datamarket.models`, one module per resource, and
  `cnovatech.datamarket.types` with the input enumerations.
- `__version__`, read from the installed package metadata.
- Guides under `docs/`: quota and costs, pagination, errors and recipes.
- Support for Python 3.10 to 3.15.
