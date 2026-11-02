# Changelog

All notable changes to `cnovatech-datamarket` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `DataMarket` and `AsyncDataMarket` clients with configuration from arguments
  or `DATAMARKET_API_KEY` / `DATAMARKET_BASE_URL`, connection pooling, context
  manager support and a `repr` that masks the key.
- `health()` on both clients: unauthenticated, free of quota cost.
- `cnovatech.datamarket.errors` with `DataMarketError` as the root of every
  exception the SDK raises.
- `cnovatech.datamarket.models` with `Health`, `Usage` and `RequestInfo`.
- `__version__`, read from the installed package metadata.
