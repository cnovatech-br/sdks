"""Resources of the Data Market API, one class per group of endpoints.

Each method builds an ``Operation`` from ``_operations`` and hands it to the
client's transport, so the synchronous and asynchronous clients share every
decision except the I/O call.
"""

from __future__ import annotations

from .account import Account, AsyncAccount
from .brands import AsyncBrands, Brands
from .products import AsyncProducts, Products
from .stores import AsyncStores, Stores

__all__ = [
    "Account",
    "AsyncAccount",
    "AsyncBrands",
    "AsyncProducts",
    "AsyncStores",
    "Brands",
    "Products",
    "Stores",
]
