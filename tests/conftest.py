"""Shared pytest marker policy for the test suite.

Tests are marked by directory so selection stays aligned with the repo layout
without repeating `pytestmark` boilerplate in every file.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Apply stable markers based on test file location."""
    for item in items:
        path = Path(str(item.fspath))
        parts = path.parts

        if "tests" not in parts:
            continue

        if "unit" in parts:
            item.add_marker(pytest.mark.unit)

        if "surface" in parts:
            item.add_marker(pytest.mark.surface)
            item.add_marker(pytest.mark.integration)

        if "stress" in parts:
            item.add_marker(pytest.mark.stress)
            item.add_marker(pytest.mark.integration)

        if "corpus" in parts:
            item.add_marker(pytest.mark.corpus)
            item.add_marker(pytest.mark.integration)

        if "e2e" in parts:
            item.add_marker(pytest.mark.e2e)
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.slow)
            item.add_marker(pytest.mark.expensive)
