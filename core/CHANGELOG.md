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
  and response interpretation. Correlation ID per request, descriptive
  `User-Agent`, `None` query parameters omitted.
- Exception hierarchy rooted at `CnovatechError`, with `APIStatusError`
  subclasses chosen by HTTP status and, for 429, by error code.
- `APIResponse` base model (immutable, keeps unknown fields) with
  `request_info`, plus `Usage` and `Health`.
