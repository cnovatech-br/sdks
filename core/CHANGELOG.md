# Changelog

All notable changes to `cnovatech-sdk-core` are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `ProductSettings` and `ClientConfig` with validation of API key, base URL
  (HTTPS required outside loopback), timeouts (read timeout capped at the
  server's 300 s) and retry count. Explicit arguments win over environment
  variables, which win over product defaults.
- `Operation`: a transport-independent description of one API call.
- `SyncTransport` and `AsyncTransport` over httpx, sharing request preparation
  and response interpretation. Correlation ID per request, kept across
  retries and reported on errors even when the API does not echo it;
  descriptive `User-Agent`; `None` query parameters omitted.
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
- `APIResponse` base model (immutable, keeps unknown fields) with
  `request_info`, plus `Usage`.
