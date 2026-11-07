# Changelog

All notable changes to `cnovatech-sdk-core` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-06

First release, together with `cnovatech-datamarket`. Rehearsed on TestPyPI as
0.1.0.dev1.

### Added

- `ProductSettings` and `ClientConfig` with validation of API key (printable
  ASCII only, so a key copied with an invisible character or a line break is
  refused before any request), base URL (HTTPS required outside loopback),
  timeouts (read timeout capped at the server's 300 s), retry count and
  budget. Explicit arguments win over environment variables, which win over
  product defaults.
- `Operation`: a transport-independent description of one API call, and
  `Endpoint`: where a call lives, declared once per endpoint.
- `BaseSyncClient` / `BaseAsyncClient` and `SyncResource` / `AsyncResource`:
  the client and resource plumbing every product SDK shares.
- `SyncTransport` and `AsyncTransport` over httpx, sharing request preparation
  and response interpretation. Correlation ID per request, kept across
  retries and reported on every error, including connection errors and
  timeouts, even when the API does not echo it; descriptive `User-Agent`;
  `None` query parameters omitted. Redirects are never followed and the
  configured timeout applies per request, also through a user-supplied
  `http_client`. Every `httpx.RequestError`, including a response body that
  cannot be decoded, becomes an `APIConnectionError`.
- `RetryPolicy`: connection failures that happen before the request is sent,
  502/503 and the per-minute 429 are repeated with capped exponential
  backoff and jitter, honouring `Retry-After`. Read timeouts, 504 (the
  application may still be processing the request), connections dropped
  mid-response, quota errors and other 4xx/5xx are never repeated. Each
  retry is logged at INFO with structured fields.
- `max_units_per_request`: an operation whose estimated cost is above the
  ceiling raises `BudgetExceededError` before anything is sent.
- Exception hierarchy rooted at `CnovatechError`, with `APIStatusError`
  subclasses chosen by HTTP status and, for 429, by error code.
  `APIConnectionError.retryable` says whether a repeat could bill twice.
  Every exception can be pickled, so it crosses process pools intact.
- `UsageTracker` and `RateLimitState`, fed by every response; a quota error
  refreshes the last known balance without counting a call.
- `APIResponse` base model (immutable, keeps unknown fields) with
  `request_info`, `Record` for nested objects, plus `Usage`, `PaginationMeta`
  and `ListMeta`.
- `SyncPage` / `AsyncPage` with `iter_pages` and `iter_all` capped by
  `max_pages` or `max_units`; pages can be pickled, without the ability to
  fetch further pages. `TabularResponse.to_dataframe()` with nested rows,
  envelope columns that collide with a row field prefixed by the response's
  name, and pandas imported on first use.
- Validation helpers accept `uuid.UUID` identifiers and any iterable of
  strings as a batch.
