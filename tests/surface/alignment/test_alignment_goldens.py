"""Exact emit goldens for alignment-policy surface fixtures."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mojo_bindgen.analysis import MojoGenerator
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.parsing.parser import ClangParser

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FIXTURES_ROOT = _REPO_ROOT / "tests" / "surface" / "alignment" / "fixtures"
_SOURCE_LINE = re.compile(r"^# source: .+$", re.MULTILINE)


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


def _case_dirs() -> list[Path]:
    return sorted(path for path in _FIXTURES_ROOT.iterdir() if path.is_dir())


def _normalize_source_line(text: str, relative_header: str) -> str:
    return _SOURCE_LINE.sub(f"# source: {relative_header}", text)


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda path: path.name)
def test_alignment_fixture_external_goldens(case_dir: Path) -> None:
    header = case_dir / "input.h"
    unit = ClangParser(header, library=case_dir.name, link_name=case_dir.name).run()
    relative_header = str(header.relative_to(_REPO_ROOT))

    strict_out = MojoGenerator(MojoEmitOptions(strict_abi=True)).generate(unit)
    strict_expected = (case_dir / "expect.strict.external.mojo").read_text(encoding="utf-8")
    assert _normalize_source_line(strict_out, relative_header) == _normalize_source_line(
        strict_expected, relative_header
    )

    portable_out = MojoGenerator(MojoEmitOptions()).generate(unit)
    portable_expected = (case_dir / "expect.portable.external.mojo").read_text(encoding="utf-8")
    assert _normalize_source_line(portable_out, relative_header) == _normalize_source_line(
        portable_expected, relative_header
    )
