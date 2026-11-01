"""Shared helpers for parser-driven stress fixtures."""

from __future__ import annotations

from pathlib import Path

from mojo_bindgen.ir import Unit
from tests.header_harness import HeaderHarness

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES_ROOT = _REPO_ROOT / "tests" / "stress" / "fixtures"


def case_dirs() -> list[Path]:
    return sorted(path for path in _FIXTURES_ROOT.iterdir() if path.is_dir())


def parse_case(case_dir: Path, bindgen: HeaderHarness) -> Unit:
    header = case_dir / "input.h"
    return bindgen.parse_header(header, library=case_dir.name, link_name=case_dir.name)
