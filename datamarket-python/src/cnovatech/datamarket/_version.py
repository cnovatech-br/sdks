"""Version of the ``cnovatech-datamarket`` distribution, read from its installed metadata."""

from __future__ import annotations

from cnovatech.sdk_core.metadata import read_distribution_version

DISTRIBUTION_NAME = "cnovatech-datamarket"

__version__ = read_distribution_version(DISTRIBUTION_NAME)
