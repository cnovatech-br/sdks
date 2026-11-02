# Fixtures

One real JSON response per live endpoint and one per error code, anonymised
and named after the endpoint's `operationId`: `healthCheck.json`,
`getCatalog.json`, `getProductByEan.json`, `error_ean_not_found.json`,
`error_insufficient_quota.json`, and so on.

`openapi.json` is the vendored OpenAPI document of the API. `test_contract.py`
uses it to verify that every live path has a method in the SDK. Refresh it with:

```bash
curl -s https://datamarket.cnovatech.com.br/openapi.json > tests/fixtures/openapi.json
```
