"""Parser-driven surface goldens for representative headers."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.parsing.parser import ClangParser

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SURFACE_ROOT = _REPO_ROOT / "tests" / "surface" / "fixtures"
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
    return sorted(p for p in _SURFACE_ROOT.iterdir() if p.is_dir())


def _normalize_source_line(text: str, relative_header: str) -> str:
    return _SOURCE_LINE.sub(f"# source: {relative_header}", text)


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_surface_fixture_external(case_dir: Path) -> None:
    header = case_dir / "input.h"
    unit = ClangParser(header, library="surface_globals", link_name="surface_globals").run()
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    expected = (case_dir / "expect.external.mojo").read_text(encoding="utf-8")
    relative_header = str(header.relative_to(_REPO_ROOT))
    assert _normalize_source_line(out, relative_header) == expected


@pytest.mark.parametrize("case_dir", _case_dirs(), ids=lambda p: p.name)
def test_surface_fixture_no_align(case_dir: Path) -> None:
    header = case_dir / "input.h"
    unit = ClangParser(header, library="surface_globals", link_name="surface_globals").run()
    out = MojoGenerator(MojoEmitOptions(emit_align=False)).generate(unit)
    expected = (case_dir / "expect.no_align.mojo").read_text(encoding="utf-8")
    relative_header = str(header.relative_to(_REPO_ROOT))
    assert _normalize_source_line(out, relative_header) == expected
