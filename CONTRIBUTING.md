# Contributing

## Setup

```bash
make install
```

This creates one virtual environment at the workspace root with every package
installed in editable mode and the development tools. `uv` resolves the
workspace, so `cnovatech-datamarket` always uses the `core` checkout next to it.

## Quality gates

`make check` runs everything CI runs:

| Step | What it enforces |
|---|---|
| `ruff check`, `ruff format --check` | Style, imports, docstrings on every public symbol, complete type hints, no `print`, no commented-out code |
| `make boundary` | `core/src` contains no product concept |
| `mypy --strict`, per package | Types, with the pydantic plugin |
| `pytest --cov`, per package | Tests pass with warnings as errors; coverage at or above 90% |

Run `make format` before committing.

## Layout

```
sdks/
├── core/                      cnovatech-sdk-core   (cnovatech.sdk_core)
├── datamarket-python/         cnovatech-datamarket (cnovatech.datamarket)
│   ├── src/cnovatech/datamarket/
│   │   ├── _client.py         DataMarket, AsyncDataMarket
│   │   ├── _config.py         ProductSettings for this API
│   │   ├── errors.py          public exceptions
│   │   ├── models/            one module per resource
│   │   └── resources/         one class per endpoint group; _operations.py defines each call
│   └── tests/                 offline tests with httpx.MockTransport; test_live.py needs --live
├── scripts/                   release checks
└── .github/workflows/         ci.yml, release.yml
```

Rules of thumb:

- A product SDK talks to the core only through `ProductSettings` and
  `Operation`. Anything that mentions an endpoint, a field or a domain term
  belongs to the product package.
- Every public symbol has a Google-style docstring. Methods that consume quota
  state the cost in their docstring.
- `None` parameters are omitted from the query string; the API treats an absent
  filter differently from an empty one.
- Input enumerations are `Literal` types; output enumerations are `str`, so new
  values from the API never break parsing.
- The API key lives in a `SecretStr`, is read only by the transport and never
  appears in `repr`, logs or exception messages.
- Code, comments and documentation are written in English.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/) with the
package as scope when the change is specific to one:
`feat(datamarket): add stores.find`, `fix(core): honour Retry-After`.
Update the package's `CHANGELOG.md` under *Unreleased* in the same change.

## Releasing

Every package carries the same version. To release:

1. Set the new version in `core/pyproject.toml` and
   `datamarket-python/pyproject.toml`, move the *Unreleased* entries of each
   `CHANGELOG.md` under the new version, and run `uv lock`.
2. Commit, then tag: `git tag v0.1.0 && git push origin v0.1.0`.
3. `release.yml` checks that the tag matches the declared versions, builds both
   packages and publishes them to TestPyPI through the `testpypi` environment.
   Publication to PyPI is enabled once the first stable release is approved.

Publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/):
no token is stored in the repository. Each package needs a pending publisher
registered on TestPyPI (and later PyPI) with owner `cnovatech`, repository
`sdks`, workflow `release.yml` and environment `testpypi`.

Installing a pre-release from TestPyPI, which does not mirror every dependency:

```bash
pip install --pre \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  cnovatech-datamarket
```
