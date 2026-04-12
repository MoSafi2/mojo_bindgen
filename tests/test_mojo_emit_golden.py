"""
Golden output for emit_unit(everything.h). Requires libclang (e.g. pixi run).

Run from repo root:
  pixi run pytest tests/test_mojo_emit_golden.py -v
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Parser emits an absolute path; golden uses a stable relative form.
_CANON_SOURCE = "# source: tests/fixtures/everything.h"
_SOURCE_LINE = re.compile(r"^# source: .+$", re.MULTILINE)


def _normalize_source_line(text: str) -> str:
    return _SOURCE_LINE.sub(_CANON_SOURCE, text)


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


def test_emit_everything_matches_golden() -> None:
    from mojo_bindgen.mojo_emit import MojoEmitOptions, emit_unit
    from mojo_bindgen.parser import ClangParser

    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    golden_path = _REPO_ROOT / "tests" / "fixtures" / "everything.mojo"
    assert header.is_file(), f"missing fixture: {header}"
    assert golden_path.is_file(), f"missing golden: {golden_path}"

    parser = ClangParser(
        header,
        library="everything",
        link_name="everything",
    )
    unit = parser.run()
    out = emit_unit(unit, MojoEmitOptions())
    expected = golden_path.read_text(encoding="utf-8")
    assert _normalize_source_line(out) == _normalize_source_line(expected)


def test_emit_everything_without_align_matches_golden() -> None:
    from mojo_bindgen.mojo_emit import MojoEmitOptions, emit_unit
    from mojo_bindgen.parser import ClangParser

    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    golden_path = _REPO_ROOT / "tests" / "fixtures" / "everything_no_align.mojo"
    assert header.is_file(), f"missing fixture: {header}"
    assert golden_path.is_file(), f"missing golden: {golden_path}"

    parser = ClangParser(
        header,
        library="everything",
        link_name="everything",
    )
    unit = parser.run()
    out = emit_unit(unit, MojoEmitOptions(emit_align=False))
    expected = golden_path.read_text(encoding="utf-8")
    assert _normalize_source_line(out) == _normalize_source_line(expected)
