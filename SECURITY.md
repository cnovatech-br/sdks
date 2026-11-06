# Security

## Reporting a vulnerability

Email <suporte@cnovatech.com.br> with the subject `SDK security`. Please do
not open a public issue for a vulnerability.

Include what you can of: the package and version, the steps or code that
reproduce the problem, and the impact you see. We confirm receipt within two
business days and keep you informed until the issue is resolved. We ask that
you give us reasonable time to publish a fix before any public disclosure.

Problems in the Data Market API itself, as opposed to these SDKs, go to the
same address.

## Supported versions

Fixes are released for the latest minor version of each package. Older
versions receive no fixes; upgrade to receive them.

## How the SDKs treat your key

- The API key is held in a `SecretStr`, read only by the transport, and sent
  only in the `X-API-Key` header over HTTPS. Plain HTTP is accepted for
  loopback addresses only.
- The key never appears in `repr`, log lines, exception messages or
  tracebacks produced by the SDK.
- The SDK installs no logging handler and reads no file: the key comes from
  the constructor argument or the environment variable, nothing else.
- Dependencies are pinned in `uv.lock` and audited in CI with `pip-audit`.

If you believe a key has been exposed, revoke it in the Data Market dashboard
and create a new one; the SDK needs no other change.
