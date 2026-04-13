"""E2E parse/emit surface checks across rich C fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.ir import Enum, Function, Struct, Typedef
from mojo_bindgen.mojo_emit import MojoEmitOptions, emit_unit
from mojo_bindgen.parser import ClangParser

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(not _has_libclang(), reason="libclang not available (use pixi run)")


def test_everything_fixture_covers_major_decl_kinds() -> None:
    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    unit = ClangParser(header, library="everything", link_name="everything").run()

    assert any(isinstance(d, Struct) and d.is_union for d in unit.decls)
    assert any(isinstance(d, Struct) and not d.is_union for d in unit.decls)
    assert any(isinstance(d, Enum) for d in unit.decls)
    assert any(isinstance(d, Typedef) for d in unit.decls)
    assert any(isinstance(d, Function) for d in unit.decls)


def test_everything_emit_contains_core_ffi_patterns() -> None:
    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    unit = ClangParser(header, library="everything", link_name="everything").run()
    out = emit_unit(unit, MojoEmitOptions())

    assert "external_call[" in out
    assert "UnsafePointer[" in out
    assert "InlineArray[" in out
    assert "struct ev_io" in out


def test_everything_emit_keeps_anon_enum_constants_as_values() -> None:
    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    unit = ClangParser(header, library="everything", link_name="everything").run()
    out = emit_unit(unit, MojoEmitOptions())

    # Anonymous enum values should be emitted as constants, not a named enum.
    assert "EV_UNDEF" in out
    assert "EV_TIMER" in out
    assert "enum anonymous" not in out
