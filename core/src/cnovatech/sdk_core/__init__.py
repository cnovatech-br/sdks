"""Shared foundation of the Cnovatech Python SDKs.

This package is not used directly by application code. The product SDKs build
on its modules (``config``, ``transport``, ``client``, ``resource``, ``models``,
``pagination``, ``errors``, ...) and re-export what their users need. It knows
nothing about any product: no endpoint, field name or domain concept lives
here, and CI enforces that boundary.
"""

from __future__ import annotations

import logging

from .config import CORE_DISTRIBUTION_NAME
from .metadata import read_distribution_version

__version__ = read_distribution_version(CORE_DISTRIBUTION_NAME)

# Libraries log but never configure logging. The null handler keeps Python from
# printing "No handlers could be found" when the application has not set up
# logging; the application routes the `cnovatech` logger wherever it wants.
logging.getLogger("cnovatech").addHandler(logging.NullHandler())

__all__ = ["__version__"]
