# Errors

Everything the SDK raises on purpose derives from `DataMarketError`, so one
`except` clause catches it all. Specific situations have specific classes.

```
DataMarketError
├── ConfigurationError            invalid or missing setting; nothing was sent
├── InvalidRequestError           an argument failed local validation; nothing was sent
├── BudgetExceededError           the call or walk would cross a quota cap; nothing was sent
├── AmbiguousStoreError           stores.find() matched several stores and none exactly
├── APIConnectionError            no usable response (DNS, TCP, TLS, dropped connection, unreadable body)
│   └── APITimeoutError           the read timeout elapsed; the call may have been billed
├── UnexpectedResponseError       the body is not the JSON the SDK expected, or a redirect
└── APIStatusError                the API answered with an error status
    ├── BadRequestError           400
    │   └── FilterRequiredError   catalogue beyond page 20 without a filter
    ├── AuthenticationError       401
    ├── TrialExpiredError         402
    ├── PermissionDeniedError     403
    ├── NotFoundError             404
    │   ├── EANNotFoundError      the code is not in the catalogue (free)
    │   └── StoreNotFoundError    unknown store_id or competitor_id, or stores.find() without a match
    ├── UnprocessableEntityError  422, with .details per field
    ├── RateLimitError            429 per minute; retried, then raised
    ├── QuotaExceededError        429 quota; never retried
    └── ServerError               5xx
```

## What an API error carries

```python
try:
    client.products.get("0000000000000")
except errors.EANNotFoundError as exc:
    exc.status_code  # 404
    exc.code  # "ean_not_found"
    exc.message  # the API's message
    exc.hint  # what the API suggests doing next, when it says
    exc.correlation_id  # quote it in support requests
    exc.usage  # the usage block, when the error carries one
    exc.retry_after  # seconds, from Retry-After, when present
    exc.body  # the decoded JSON body
```

`str(exc)` combines status, code, message, hint and correlation ID. The API
key never appears in a message, a log line or a traceback.

`APIConnectionError` and `APITimeoutError` carry the `correlation_id` the SDK
sent with the request, even though no response came back. Quote it to ask
support whether a timed-out call was billed. A quota error also refreshes
`client.usage.last` with the balance it reports.

Every exception can be pickled, so it crosses process pools and error
reporters intact.

## What is retried

Before raising, the SDK repeats a call up to `max_retries` times (two by
default) only when the repeat cannot bill the account twice:

- connection failures that happen before the request is sent;
- 502 and 503, which come from the gateway before the application answers,
  waiting for `Retry-After` when the gateway sends one;
- 429 `rate_limit_exceeded`, waiting the seconds the API asks for.

Never retried: read timeouts and connections dropped while the response was
being read (the request may have been processed), a response that arrived but
could not be read, 504 (the gateway gave up while the application may still be
working), 500, every other 4xx and all quota errors. Each retry is logged at
INFO on the `cnovatech` logger.

## Handling the common cases

```python
from cnovatech.datamarket import DataMarket, errors

client = DataMarket()

try:
    product = client.products.get(ean, state="SP")
except errors.EANNotFoundError:
    ...  # not in the catalogue; free. Check many codes at once with products.coverage()
except errors.InvalidRequestError as exc:
    ...  # the argument was malformed; nothing was sent
except errors.QuotaExceededError as exc:
    ...  # stop the job; exc.upgrade_url and exc.early_renewal_url say what to do
except errors.APITimeoutError:
    ...  # may have been billed: check client.account.usage() before repeating
except errors.RateLimitError as exc:
    ...  # the retries were not enough; wait exc.retry_after seconds
except errors.APIStatusError as exc:
    ...  # any other answer from the API; exc.correlation_id for support
except errors.DataMarketError:
    ...  # anything else the SDK raises
```

## Local errors

`ConfigurationError` comes from the constructor or from the first
authenticated call without a key: an invalid `base_url`, a timeout out of
range, no API key, a key with characters that cannot travel in an HTTP header
(an invisible character or a line break copied along with it).
`InvalidRequestError` comes from an argument the SDK can tell is wrong before
sending: a malformed EAN, a store identifier that is not a UUID, a page below
1, a `limit` above the endpoint's maximum, more than 500 codes in a coverage
check, a blank name in `stores.find()`. Both are also `ValueError`.

Value ranges the API validates itself, such as percentages, are left to it:
the 422 answer names the field and the rule in `UnprocessableEntityError.details`.

## Unexpected responses

`UnexpectedResponseError` means the response was not the JSON the SDK
expected. The usual cause is a wrong `base_url`: paths the API does not know
are answered by the web application with HTML and status 200, or with a
redirect, which the SDK never follows (the key would travel with it). The
exception carries `status_code` and `content_type`.

## Looking up a store by name

`stores.find(name)` reads up to five pages of search results until a store
name matches exactly, ignoring case. With no exact match and one candidate,
that candidate is returned. With none, `StoreNotFoundError`. With several,
`AmbiguousStoreError` with the candidates, so the caller can narrow the
search with `state=` or `city=`, or pick one by `store_id`.
