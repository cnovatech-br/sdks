"""Package metadata helpers."""

from __future__ import annotations

import functools
from importlib.metadata import PackageNotFoundError, version

UNKNOWN_VERSION = "0.0.0+unknown"


@functools.cache
def read_distribution_version(distribution_name: str) -> str:
    """Return the installed version of a distribution.

    The version is declared once, in ``pyproject.toml``, and read back from the
    installed metadata so there is no second copy to keep in sync. The sentinel
    keeps imports working from a source checkout that was never installed. The
    lookup scans the installed packages, so its result is cached.
    """
    try:
        return version(distribution_name)
    except PackageNotFoundError:
        return UNKNOWN_VERSION
