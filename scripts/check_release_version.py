"""Verify that a release tag matches every workspace package.

Each package must declare the tagged version in ``pyproject.toml`` and have a
``## [version]`` section in its ``CHANGELOG.md``.

Usage::

    python scripts/check_release_version.py v0.1.0

Exits with status 1 and lists the problems when any package disagrees. When
``GITHUB_OUTPUT`` is set, writes ``final=true`` for a final version such as
``1.2.3`` and ``final=false`` for a pre-release, so the release workflow can
stop pre-releases at TestPyPI. Requires Python 3.11 or newer for ``tomllib``.
"""

from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIRECTORIES = (
    WORKSPACE_ROOT / "core",
    WORKSPACE_ROOT / "datamarket-python",
)
FINAL_VERSION = re.compile(r"^\d+\.\d+\.\d+$")


def declared_version(package: Path) -> str:
    """Read ``project.version`` from the package's ``pyproject.toml``."""
    with (package / "pyproject.toml").open("rb") as handle:
        version: str = tomllib.load(handle)["project"]["version"]
    return version


def has_changelog_section(package: Path, version: str) -> bool:
    """Whether the package's ``CHANGELOG.md`` has a ``## [version]`` heading."""
    heading = re.compile(rf"^## \[{re.escape(version)}\]", re.MULTILINE)
    return heading.search((package / "CHANGELOG.md").read_text(encoding="utf-8")) is not None


def problems(expected: str) -> list[str]:
    """Every package that does not declare or document ``expected``."""
    found: list[str] = []
    for package in PACKAGE_DIRECTORIES:
        name = package.relative_to(WORKSPACE_ROOT)
        if (version := declared_version(package)) != expected:
            found.append(f"{name}/pyproject.toml declares {version}")
        if not has_changelog_section(package, expected):
            found.append(f"{name}/CHANGELOG.md has no '## [{expected}]' section")
    return found


def report_release_kind(version: str) -> None:
    """Say whether ``version`` is final, to the console and to ``GITHUB_OUTPUT`` when set."""
    final = FINAL_VERSION.match(version) is not None
    print(f"{version} is a {'final version' if final else 'pre-release'}.")
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as handle:
            handle.write(f"final={'true' if final else 'false'}\n")


def main(argv: list[str]) -> int:
    """Compare the tag in ``argv[1]`` with every package."""
    if len(argv) != 2:
        print(__doc__)
        return 2
    expected = argv[1].removeprefix("v")
    if found := problems(expected):
        print(f"Tag {argv[1]} expects version {expected}, but:")
        for problem in found:
            print(f"  {problem}")
        return 1
    print(f"Every package declares and documents {expected}.")
    report_release_kind(expected)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
