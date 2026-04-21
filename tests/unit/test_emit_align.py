"""Tests for principled record layout alignment and fallback emission."""

from __future__ import annotations

from pathlib import Path

import pytest

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.render import render_struct
from mojo_bindgen.ir import Field, IntKind, IntType, Struct
from mojo_bindgen.analysis.analyze_for_mojo import analyzed_struct_for_test, struct_by_decl_id

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


def test_packed_aligned_record_falls_back_to_opaque_storage() -> None:
    from mojo_bindgen.parsing.parser import ClangParser

    header = (
        _REPO_ROOT / "tests" / "stress" / "fixtures" / "pathological_layout" / "input.h"
    )
    parser = ClangParser(header, library="pathological_layout", link_name="pathological_layout")
    unit = parser.run()
    orig = next(d for d in unit.decls if getattr(d, "c_name", None) == "pl_packed_aligned")
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
    opts = MojoEmitOptions(warn_abi=False, strict_abi=True)
    analyzed = analyzed_struct_for_test(
        patched,
        struct_by_name=struct_by_name,
        options=opts,
    )
    text = render_struct(analyzed, opts)
    assert analyzed.representation_mode == "opaque_storage_exact"
    assert "@align(16)" in text
    assert "var storage: InlineArray[UInt8, 20]" in text
    assert "not representable as a typed Mojo struct" in text


def test_default_portable_mode_omits_plain_struct_align() -> None:
    p = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    f = Field(name="x", source_name="x", type=p, byte_offset=0)
    plain = Struct(
        decl_id="plain_align",
        name="plain_align",
        c_name="plain_align",
        fields=[f],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    opts = MojoEmitOptions(warn_abi=False)
    analyzed = analyzed_struct_for_test(
        plain,
        struct_by_name={plain.decl_id: plain},
        options=opts,
    )
    text = render_struct(analyzed, opts)
    assert analyzed.representation_mode == "fieldwise_exact"
    assert "@align(" not in text


def test_align_omitted_comment_for_invalid_explicit_c_align_bytes() -> None:
    """Non-power-of-two explicit alignment cannot be expressed as an exact typed layout."""
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
        requested_align_bytes=3,
    )
    opts = MojoEmitOptions(warn_abi=False)
    analyzed = analyzed_struct_for_test(
        bad,
        struct_by_name={bad.decl_id: bad},
        options=opts,
    )
    text = render_struct(analyzed, opts)
    assert analyzed.representation_mode == "opaque_storage_exact"
    assert "@align(" not in text
    assert "align_bytes=3" in text
    assert "omitted" in text
    assert "InlineArray[UInt8, 8]" in text


def test_strict_abi_mode_preserves_plain_struct_align() -> None:
    p = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    f = Field(name="x", source_name="x", type=p, byte_offset=0)
    plain = Struct(
        decl_id="strict_plain_align",
        name="strict_plain_align",
        c_name="strict_plain_align",
        fields=[f],
        size_bytes=8,
        align_bytes=8,
        is_union=False,
    )
    opts = MojoEmitOptions(warn_abi=False, strict_abi=True)
    analyzed = analyzed_struct_for_test(
        plain,
        struct_by_name={plain.decl_id: plain},
        options=opts,
    )
    text = render_struct(analyzed, opts)
    assert analyzed.representation_mode == "fieldwise_padded_exact"
    assert "@align(8)" in text
    assert "var __pad0: InlineArray[UInt8, 4]" in text


def test_explicit_overalignment_uses_trailing_padding() -> None:
    c_char = IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1)
    c_int = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    st = Struct(
        decl_id="explicit_padded",
        name="explicit_padded",
        c_name="explicit_padded",
        fields=[
            Field(name="tag", source_name="tag", type=c_char, byte_offset=0),
            Field(name="value", source_name="value", type=c_int, byte_offset=4),
        ],
        size_bytes=16,
        align_bytes=16,
        is_union=False,
        requested_align_bytes=16,
    )
    analyzed = analyzed_struct_for_test(
        st,
        struct_by_name={st.decl_id: st},
        options=MojoEmitOptions(warn_abi=False),
    )
    text = render_struct(analyzed, MojoEmitOptions(warn_abi=False))
    assert analyzed.representation_mode == "fieldwise_padded_exact"
    assert "@align(16)" in text
    assert "var value: c_int" in text
    assert "var __pad0: InlineArray[UInt8, 8]" in text
    assert "trailing padding" in text


def test_field_alignment_uses_interior_and_trailing_padding() -> None:
    c_char = IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1)
    c_int = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    st = Struct(
        decl_id="field_aligned",
        name="field_aligned",
        c_name="field_aligned",
        fields=[
            Field(name="tag", source_name="tag", type=c_char, byte_offset=0),
            Field(name="value", source_name="value", type=c_int, byte_offset=16),
        ],
        size_bytes=32,
        align_bytes=16,
        is_union=False,
    )
    analyzed = analyzed_struct_for_test(
        st,
        struct_by_name={st.decl_id: st},
        options=MojoEmitOptions(warn_abi=False),
    )
    text = render_struct(analyzed, MojoEmitOptions(warn_abi=False))
    assert analyzed.representation_mode == "fieldwise_padded_exact"
    assert "@align(16)" in text
    assert "synthesized padding: bytes 4..15" in text
    assert "synthesized trailing padding: bytes 20..31" in text


def test_pragma_pack2_falls_back_to_opaque_storage_without_typed_fields() -> None:
    c_char = IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1)
    c_int = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    st = Struct(
        decl_id="pragma_pack2",
        name="pragma_pack2",
        c_name="pragma_pack2",
        fields=[
            Field(name="tag", source_name="tag", type=c_char, byte_offset=0),
            Field(name="value", source_name="value", type=c_int, byte_offset=2),
        ],
        size_bytes=6,
        align_bytes=2,
        is_union=False,
    )
    analyzed = analyzed_struct_for_test(
        st,
        struct_by_name={st.decl_id: st},
        options=MojoEmitOptions(warn_abi=False),
    )
    text = render_struct(analyzed, MojoEmitOptions(warn_abi=False))
    assert analyzed.representation_mode == "opaque_storage_exact"
    assert "var storage: InlineArray[UInt8, 6]" in text
    assert "var value: c_int" not in text
