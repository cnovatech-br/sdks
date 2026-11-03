# Fixtures

One JSON response per endpoint and one per error code the SDK handles
specially, named after the endpoint's `operationId`: `healthCheck.json`,
`getCatalog.json`, `getProductByEan.json`, `error_ean_not_found.json`, and so on.

They are captured from production through the SDK itself and anonymised
(account identity, IP addresses and key prefixes are replaced). Refresh them
from the workspace root, with `DATAMARKET_API_KEY` set or present in `.env`:

```bash
make capture   # about 21 quota units
```

Until the first capture runs, the files are hand-written from the API's
OpenAPI document and follow its schemas field by field.

`openapi.json` is the OpenAPI document of the API. `test_contract.py` uses it
to verify that every live, read-only operation has a counterpart in the SDK.
Refresh it with:

```bash
curl -s https://datamarket.cnovatech.com.br/openapi.json > tests/fixtures/openapi.json
```
