# cnovatech-sdk-core

Shared foundation of the Cnovatech Python SDKs: configuration, HTTP transport
(sync and async), error hierarchy, pagination and quota accounting.

This package is not meant to be installed on its own. Product SDKs such as
[`cnovatech-datamarket`](../datamarket-python/) depend on it and re-export
everything their users need. If you are integrating with a Cnovatech API,
install the product SDK.

## Boundary

The core knows nothing about any product: no endpoint, no field name, no domain
concept. CI fails if a product term appears under `core/src`. Product-specific
behaviour reaches the core only through `ProductSettings` (environment prefix,
base URL, API prefix, error overrides) and `Operation` objects built by the
product's resources.

## Versioning

The core and the product SDKs are released together and share a version number.
A product SDK pins the core to the same minor series.
