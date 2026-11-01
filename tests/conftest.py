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


pytest_plugins = ["tests.header_harness"]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--bindgen",
        choices=("all", "python", "native"),
        default="all",
        help="Generators for shared acceptance suites (native runs O0 and O3).",
    )


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "bindgen" not in metafunc.fixturenames:
        return
    selected = metafunc.config.getoption("--bindgen")
    implementations = []
    if selected != "native":
        implementations.append(pytest.param("python", id="python"))
    if selected != "python":
        implementations.extend(
            pytest.param(name, id=name, marks=(pytest.mark.native, pytest.mark.expensive))
            for name in ("native-O0", "native-O3")
        )
    metafunc.parametrize("bindgen", implementations, indirect=True, scope="session")
