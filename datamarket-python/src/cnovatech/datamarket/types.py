"""Input enumerations of the Data Market API, as ``Literal`` types.

They give editors completion and let type checkers catch a wrong value before
the request is sent. Output fields with the same vocabulary are plain strings,
so a value the API adds later never breaks parsing.
"""

from __future__ import annotations

from typing import Literal

Channel = Literal["e-commerce", "delivery"]
"""Sales channel of a store."""

MarketScope = Literal["all", "same_state", "neighbors"]
"""Which stores make up the market: the whole country, the store's state, or that state and its neighbours."""

Granularity = Literal["daily", "weekly", "monthly"]
"""Period of a price history series."""

OpportunityType = Literal["increase", "decrease", "comfortable"]
"""Repricing opportunity: price can go up, is above the market, or sits within the band."""

PricePosition = Literal["all", "below", "aligned", "above", "unavailable"]
"""Filter of a comparison by price position against the competitor."""

OfferSortBy = Literal["price", "store_name", "available"]
"""Ordering of the offers of a product."""

ComparisonSortBy = Literal["price_diff_pct", "product_name", "category"]
"""Ordering of a product-by-product comparison."""

SortOrder = Literal["asc", "desc"]
"""Ascending or descending."""

LogStatus = Literal["success", "error"]
"""Outcome filter of the request log: 2xx responses, or 4xx and above."""
