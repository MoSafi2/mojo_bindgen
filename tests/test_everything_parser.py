"""
Parse tests/fixtures/everything.h and print the resulting Unit (stdlib unittest, no pytest).

Run from repo root:
  python -m unittest tests.test_everything_parser -v
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.parser import ClangParser


def _system_compile_args() -> list[str]:
    """Headers such as stddef.h often live under the compiler's include directory."""
    args = ["-I/usr/include"]
    try:
        out = subprocess.check_output(
            ["cc", "-print-file-name=include"], text=True, timeout=10
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return args
    if out and out != "include" and Path(out).is_dir():
        args.append(f"-I{out}")
    return args


class TestEverythingParser(unittest.TestCase):
    def test_parse_fixture_prints_unit(self) -> None:
        header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
        self.assertTrue(header.is_file(), f"missing fixture: {header}")

        parser = ClangParser(
            header,
            library="everything",
            link_name="everything",
            compile_args=_system_compile_args(),
        )
        unit = parser.run()
        print(unit)


if __name__ == "__main__":
    unittest.main()
