# Cnovatech Python SDKs

Official Python clients for the Cnovatech data APIs, developed as a single
[uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/).

| Package | Import | Purpose |
|---|---|---|
| [`cnovatech-datamarket`](datamarket-python/) | `cnovatech.datamarket` | Data Market: price, availability and assortment intelligence for Brazilian supermarkets |
| [`cnovatech-sdk-core`](core/) | `cnovatech.sdk_core` | Shared transport, configuration, errors and pagination. Installed as a dependency; not used directly |

All packages share the `cnovatech` namespace and are released together under
one version number.

## Install

```bash
pip install cnovatech-datamarket
```

See each package's README for usage.

## Develop

Requirements: [uv](https://docs.astral.sh/uv/) 0.5 or newer and `make`.

```bash
make install     # one virtualenv for every package plus the dev tools
make check       # ruff, boundary check, mypy --strict, tests with coverage
make live        # smoke test against the real API; free endpoints only
```

Contribution guidelines, layout and the release process are in
[CONTRIBUTING.md](CONTRIBUTING.md). To report a vulnerability, see
[SECURITY.md](SECURITY.md).
