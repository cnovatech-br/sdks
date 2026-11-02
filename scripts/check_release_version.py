"""Verify that every workspace package declares the version named by a release tag.

Usage::

    python scripts/check_release_version.py v0.1.0

Exits with status 1 and lists the mismatches when any package disagrees.
Requires Python 3.11 or newer for ``tomllib``.
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_MANIFESTS = (
    WORKSPACE_ROOT / "core" / "pyproject.toml",
    WORKSPACE_ROOT / "datamarket-python" / "pyproject.toml",
)


def declared_version(manifest: Path) -> str:
    """Read ``project.version`` from a ``pyproject.toml``."""
    with manifest.open("rb") as handle:
        version: str = tomllib.load(handle)["project"]["version"]
    return version


def main(argv: list[str]) -> int:
    """Compare the tag in ``argv[1]`` with every package version."""
    if len(argv) != 2:
        print(__doc__)
        return 2
    expected = argv[1].removeprefix("v")
    mismatches = [
        f"{manifest.relative_to(WORKSPACE_ROOT)}: {version}"
        for manifest in PACKAGE_MANIFESTS
        if (version := declared_version(manifest)) != expected
    ]
    if mismatches:
        print(f"Tag {argv[1]} expects version {expected}, but:")
        for mismatch in mismatches:
            print(f"  {mismatch}")
        return 1
    print(f"Every package declares {expected}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
