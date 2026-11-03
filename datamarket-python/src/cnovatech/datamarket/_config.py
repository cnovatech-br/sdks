"""Settings that bind the shared core to the Data Market API."""

from __future__ import annotations

from cnovatech.sdk_core.config import ProductSettings

from ._version import DISTRIBUTION_NAME, __version__
from .errors import EANNotFoundError, FilterRequiredError

PRODUCTION_BASE_URL = "https://datamarket.cnovatech.com.br"
API_PREFIX = "/api/v1"
ENV_PREFIX = "DATAMARKET_"

PRODUCT_SETTINGS = ProductSettings(
    distribution_name=DISTRIBUTION_NAME,
    version=__version__,
    env_prefix=ENV_PREFIX,
    default_base_url=PRODUCTION_BASE_URL,
    api_prefix=API_PREFIX,
    error_overrides={
        "ean_not_found": EANNotFoundError,
        "filter_required": FilterRequiredError,
    },
)
