"""The API key never leaves the client through anything a user might print, log or report."""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

from cnovatech.datamarket import errors

if TYPE_CHECKING:
    import pytest
    from conftest import FakeAPI

SECRET = "dm_verysecretkey1234567890"


def test_the_key_never_appears_in_repr_logs_or_tracebacks(
    api: FakeAPI, caplog: pytest.LogCaptureFixture
) -> None:
    api.respond(
        "GET",
        "/api/v1/user/profile",
        {"error": "unauthorized", "message": "Invalid or revoked API key."},
        status_code=401,
    )
    surfaces: list[str] = []

    with caplog.at_level(logging.DEBUG, logger="cnovatech"), api.client(api_key=SECRET) as client:
        surfaces.append(repr(client))
        surfaces.append(repr(client.usage))
        try:
            client.account.profile()
        except errors.AuthenticationError as exc:
            surfaces.append(str(exc))
            surfaces.append(repr(exc))
            surfaces.append("".join(traceback.format_exception(exc)))
    surfaces.append(caplog.text)

    assert api.last_request.headers["X-API-Key"] == SECRET, "the key is sent, as a header"
    assert surfaces, "every surface was collected"
    for surface in surfaces:
        assert SECRET not in surface
        assert "verysecret" not in surface
    assert "dm_****" in surfaces[0]
