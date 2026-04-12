"""Tests for @align emission (MojoEmitOptions.emit_align)."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.ir import Field, Primitive, PrimitiveKind, Struct
from mojo_bindgen.mojo_emit import MojoEmitOptions, _emit_struct

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


def test_stride_comment_when_size_not_multiple_of_align() -> None:
    """Covers the FFI array-stride warning (size_of stride vs align_of)."""
    from mojo_bindgen.parser import ClangParser

    header = _REPO_ROOT / "tests" / "fixtures" / "everything.h"
    parser = ClangParser(header, library="everything", link_name="everything")
    unit = parser.run()
    orig = next(d for d in unit.decls if getattr(d, "c_name", None) == "ev_aligned_data")
    assert isinstance(orig, Struct)
    patched = Struct(
        name=orig.name,
        c_name=orig.c_name,
        fields=orig.fields,
        size_bytes=20,
        align_bytes=16,
        is_union=orig.is_union,
    )
    text = _emit_struct(
        patched,
        MojoEmitOptions(emit_align=True, warn_abi=False),
        {},
        None,
    )
    assert "@align(16)" in text
    assert "FFI: array stride" in text


def test_align_omitted_comment_for_invalid_c_align_bytes() -> None:
    """Non-power-of-two alignment cannot be expressed as Mojo @align."""
    p = Primitive(
        kind=PrimitiveKind.INT,
        size_bytes=4,
        is_signed=True,
        name="int",
    )
    f = Field(name="x", type=p, byte_offset=0)
    bad = Struct(
        name="bad_align",
        c_name="bad_align",
        fields=[f],
        size_bytes=8,
        align_bytes=3,
        is_union=False,
    )
    text = _emit_struct(
        bad,
        MojoEmitOptions(emit_align=True, warn_abi=False),
        {},
        None,
    )
    assert "@align(" not in text
    assert "align_bytes=3" in text
    assert "omitted" in text
