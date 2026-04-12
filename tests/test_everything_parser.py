"""
Parse tests/fixtures/everything.h and print the resulting Unit (stdlib unittest, no pytest).

Run from repo root:
  python -m unittest tests.test_everything_parser -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.parser import ClangParser


class TestEverythingParser(unittest.TestCase):
    def test_parse_fixture_prints_unit(self) -> None:
        header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
        self.assertTrue(header.is_file(), f"missing fixture: {header}")

        parser = ClangParser(
            header,
            library="everything",
            link_name="everything",
        )
        unit = parser.run()
        print(unit.to_json())


if __name__ == "__main__":
    unittest.main()

