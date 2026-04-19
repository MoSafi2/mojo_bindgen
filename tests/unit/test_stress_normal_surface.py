"""Parse stress fixtures and compare emitted Mojo against broad goldens."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.parsing.parser import ClangParser

_REPO_ROOT = Path(__file__).resolve().parents[2]

_CANON_SOURCE = "# source: tests/stress/normal/stress_normal_input.h"
_SOURCE_LINE = re.compile(r"^# source: .+$", re.MULTILINE)


def _normalize_source_line(text: str) -> str:
    return _SOURCE_LINE.sub(_CANON_SOURCE, text)


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


def test_parse_stress_normal_fixture_prints_unit() -> None:
    header = _REPO_ROOT / "tests" / "stress" / "normal" / "stress_normal_input.h"
    assert header.is_file(), f"missing fixture: {header}"

    parser = ClangParser(
        header,
        library="stress_normal",
        link_name="stress_normal",
    )
    unit = parser.run()
    print(unit.to_json())


def test_emit_stress_normal_matches_golden() -> None:
    header = _REPO_ROOT / "tests" / "stress" / "normal" / "stress_normal_input.h"
    golden_path = _REPO_ROOT / "tests" / "stress" / "normal" / "stress_normal_external.mojo"
    assert header.is_file(), f"missing fixture: {header}"
    assert golden_path.is_file(), f"missing golden: {golden_path}"

    parser = ClangParser(
        header,
        library="stress_normal",
        link_name="stress_normal",
    )
    unit = parser.run()
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    expected = golden_path.read_text(encoding="utf-8")
    assert _normalize_source_line(out) == _normalize_source_line(expected)
