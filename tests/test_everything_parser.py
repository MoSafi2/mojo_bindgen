"""
Parse tests/fixtures/everything.h and print the resulting Unit.

Run from repo root:
  pixi run pytest tests/test_everything_parser.py -v -s
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.parser import ClangParser

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_libclang(),
    reason="libclang not available (use pixi run)",
)


def test_parse_fixture_prints_unit() -> None:
    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    assert header.is_file(), f"missing fixture: {header}"

    parser = ClangParser(
        header,
        library="everything",
        link_name="everything",
    )
    unit = parser.run()
    print(unit.to_json())


if __name__ == "__main__":
    test_parse_fixture_prints_unit()