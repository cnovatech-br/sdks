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

Run `make format` before committing. CI runs the same steps on every supported
Python (`make matrix` does it locally), audits the locked dependencies, and
builds both packages, installs the wheels into a clean environment and imports
them from outside the checkout, so a packaging mistake fails before a release.

Two targets reach the real API and need a key. Copy `.env.example` to `.env`
at the workspace root, which git ignores, and put the key there:

```
DATAMARKET_API_KEY=dm_...
```

`make live` runs the smoke tests (free endpoints only) and `make capture`
calls every endpoint once through the SDK and refreshes the test fixtures
(about 21 quota units); run it before every release, so the fixtures and the
contract test reflect what the API returns today. Use a key of an ordinary
account, not an administrative one, so that quota and rate-limit information
behaves as it does for users. Any script runs the same way:

```bash
uv run --env-file .env python script.py
```

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
├── scripts/                   release checks and the fixture capture
└── .github/                   workflows (ci.yml, release.yml), Dependabot, issue and PR templates, CODEOWNERS
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

## Versioning and support

- Every package carries the same version number and they are released together.
- Before 1.0, a minor release (`0.x`) may change the public surface; every such
  change is listed under *Changed* or *Removed* in the changelog. From 1.0 the
  project follows [Semantic Versioning](https://semver.org/).
- A deprecated name keeps working and emits `DeprecationWarning` for at least
  two minor releases before it is removed.
- `cnovatech.sdk_core` is internal to the product SDKs. It is published so that
  they can depend on it, but it makes no stability promise; user code imports
  from `cnovatech.datamarket` only.
- The supported Python versions are the ones in the CI test matrix. A version
  is dropped in a minor release, announced in the changelog.
- Fixes land on the latest release only; see [SECURITY.md](SECURITY.md) for
  vulnerability reports.

## Branch protection

`main` accepts pull requests only, reviewed by a code owner
(`.github/CODEOWNERS`), with these checks required: *Lint and boundary*,
*Type check*, every *Test ... on Python ...* job, *Build and install* and
*Dependency audit*.

## Releasing

To release:

1. Run `make capture` and commit any fixture change.
2. Set the new version in `core/pyproject.toml` and
   `datamarket-python/pyproject.toml`, move the *Unreleased* entries of each
   `CHANGELOG.md` under a `## [version]` heading with the date, and run
   `uv lock`.
3. Commit, then tag: `git tag v0.1.0 && git push origin v0.1.0`.
4. `release.yml` checks that both packages declare the tagged version and have
   a changelog section for it, runs the whole CI workflow as its quality gate,
   and publishes the distributions built there to TestPyPI through the
   `testpypi` environment, with PEP 740 attestations. Publication to PyPI is
   enabled once the first stable release is approved.

Dependabot proposes weekly updates to the pinned GitHub Actions and to
`uv.lock` (`.github/dependabot.yml`); actions are pinned by commit SHA with the
version in a comment.

Publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/):
no token is stored in the repository. Each package needs a pending publisher
registered on TestPyPI (and later PyPI) with owner `cnovatech-br`, repository
`sdks`, workflow `release.yml` and environment `testpypi`.

Installing a pre-release from TestPyPI, which does not mirror every dependency:

```bash
pip install --pre \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ \
  cnovatech-datamarket
```
