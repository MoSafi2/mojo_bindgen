"""Shared helpers for parser-driven stress fixtures."""

from __future__ import annotations

from pathlib import Path

from mojo_bindgen.parsing.parser import ClangParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_FIXTURES_ROOT = _REPO_ROOT / "tests" / "stress" / "fixtures"


def has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


def case_dirs() -> list[Path]:
    return sorted(path for path in _FIXTURES_ROOT.iterdir() if path.is_dir())


def parse_case(case_dir: Path):
    header = case_dir / "input.h"
    return ClangParser(header, library=case_dir.name, link_name=case_dir.name).run()
