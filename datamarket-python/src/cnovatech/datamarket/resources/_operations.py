"""Operation definitions, one function per API endpoint.

Everything an endpoint needs, from its path to its quota estimate, is declared
here and nowhere else. Resources call these functions; transports execute the
result.
"""

from __future__ import annotations

from cnovatech.datamarket.models import Health
from cnovatech.sdk_core.models import parser_for
from cnovatech.sdk_core.operation import Operation


def health() -> Operation[Health]:
    """``GET /health``: availability of the API, its database and its cache.

    Served outside the versioned API prefix, without authentication and
    without quota cost.
    """
    return Operation(
        method="GET",
        path="/health",
        parse=parser_for(Health),
        requires_auth=False,
        under_api_prefix=False,
    )
