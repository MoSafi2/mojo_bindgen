"""Tests for @align emission from C struct alignment."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.render import render_struct
from mojo_bindgen.ir import Field, IntKind, IntType, Struct
from mojo_bindgen.passes.analyze_for_mojo import analyzed_struct_for_test, struct_by_decl_id

_REPO_ROOT = Path(__file__).resolve().parents[2]


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
    from mojo_bindgen.parsing.parser import ClangParser

    header = _REPO_ROOT / "tests" / "stress" / "normal" / "stress_normal_input.h"
    parser = ClangParser(header, library="stress_normal", link_name="stress_normal")
    unit = parser.run()
    orig = next(d for d in unit.decls if getattr(d, "c_name", None) == "ev_aligned_data")
    assert isinstance(orig, Struct)
    patched = Struct(
        decl_id=orig.decl_id,
        name=orig.name,
        c_name=orig.c_name,
        fields=orig.fields,
        size_bytes=20,
        align_bytes=16,
        is_union=orig.is_union,
        is_anonymous=orig.is_anonymous,
        is_complete=orig.is_complete,
        is_packed=orig.is_packed,
        requested_align_bytes=orig.requested_align_bytes,
    )
    struct_by_name = dict(struct_by_decl_id(unit))
    struct_by_name[patched.decl_id] = patched
    opts = MojoEmitOptions(warn_abi=False)
    analyzed = analyzed_struct_for_test(
        patched,
        struct_by_name=struct_by_name,
    )
    text = render_struct(analyzed, opts)
    assert "@align(16)" in text
    assert "FFI: array stride" in text


def test_align_omitted_comment_for_invalid_c_align_bytes() -> None:
    """Non-power-of-two alignment cannot be expressed as Mojo @align."""
    p = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    f = Field(name="x", source_name="x", type=p, byte_offset=0)
    bad = Struct(
        decl_id="bad_align",
        name="bad_align",
        c_name="bad_align",
        fields=[f],
        size_bytes=8,
        align_bytes=3,
        is_union=False,
    )
    opts = MojoEmitOptions(warn_abi=False)
    analyzed = analyzed_struct_for_test(
        bad,
        struct_by_name={bad.decl_id: bad},
    )
    text = render_struct(analyzed, opts)
    assert "@align(" not in text
    assert "align_bytes=3" in text
    assert "omitted" in text
