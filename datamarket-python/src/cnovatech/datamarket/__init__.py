"""Official Python SDK for the Cnovatech Data Market API.

Typical use::

    from cnovatech.datamarket import DataMarket

    with DataMarket() as client:  # reads DATAMARKET_API_KEY
        product = client.products.get("7894900011517", state="SP")
        print(product.market.median_price, product.usage.remaining)

``AsyncDataMarket`` offers the same surface with coroutines.
"""

from __future__ import annotations

from . import errors, models, types
from ._client import AsyncDataMarket, DataMarket
from ._version import __version__

__all__ = ["AsyncDataMarket", "DataMarket", "__version__", "errors", "models", "types"]
