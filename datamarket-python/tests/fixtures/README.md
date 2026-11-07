# Fixtures

One JSON response per endpoint, one per error code the SDK handles specially
and one for the validation error every 422 shares, named after the endpoint's
`operationId` or the error code: `healthCheck.json`, `getCatalog.json`,
`getProductByEan.json`, `error_ean_not_found.json`, `error_validation_error.json`,
and so on.

They are captured from production through the SDK itself, anonymised
(account identity, IP addresses and key prefixes are replaced) and trimmed:
every list keeps its first five items, while counts in `summary` and `meta`
still describe the full response. `test_models.py` checks that each one
parses into its model and serialises back unchanged. The market data they
contain is a sample of what the API serves to every customer, published here
with Cnovatech's authorisation for testing and documentation only; it is not
licensed for any other use.

Refresh them from the workspace root, with `DATAMARKET_API_KEY` set or
present in `.env`:

```bash
make capture   # about 21 quota units
```

`openapi.json` is the OpenAPI document of the API. `test_contract.py` uses it
to verify that every live, read-only operation has a counterpart in the SDK.
Refresh it with:

```bash
curl -s https://datamarket.cnovatech.com.br/openapi.json > tests/fixtures/openapi.json
```
