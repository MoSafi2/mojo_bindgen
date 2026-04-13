"""Focused IR and codegen tests for newer parser/model features."""

from __future__ import annotations

from mojo_bindgen.codegen.analysis import analyze_unit
from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.lowering import lower_type
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    Const,
    GlobalVar,
    IntLiteral,
    OpaqueRecordRef,
    Primitive,
    PrimitiveKind,
    StringLiteral,
    Struct,
    Unit,
    UnsupportedType,
)


def _i32() -> Primitive:
    return Primitive(name="int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)


def test_lower_opaque_record_ref_as_opaque_pointer() -> None:
    t = OpaqueRecordRef(decl_id="struct:FILE", name="FILE", c_name="FILE")
    assert lower_type(t, ffi_origin="external") == "MutOpaquePointer[MutExternalOrigin]"


def test_lower_unsupported_type_with_size_becomes_inline_bytes() -> None:
    t = UnsupportedType(
        category="unsupported_extension",
        spelling="mystery_t",
        reason="not modeled",
        size_bytes=16,
    )
    assert lower_type(t, ffi_origin="external") == "InlineArray[UInt8, 16]"


def test_incomplete_struct_is_not_emitted_as_ordered_struct() -> None:
    st = Struct(
        decl_id="struct:foo",
        name="foo",
        c_name="foo",
        fields=[],
        size_bytes=0,
        align_bytes=0,
        is_complete=False,
    )
    au = analyze_unit(Unit(source_header="t.h", library="t", link_name="t", decls=[st]), MojoEmitOptions())
    assert au.ordered_structs == ()


def test_generator_renders_global_var_stub_and_string_const() -> None:
    i32 = _i32()
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            GlobalVar(
                decl_id="var:global_counter",
                name="global_counter",
                link_name="global_counter",
                type=i32,
            ),
            Const(
                name="LIB_NAME",
                type=Primitive(name="char", kind=PrimitiveKind.CHAR, is_signed=True, size_bytes=1),
                expr=StringLiteral("bindgen"),
            ),
            Const(name="LIMIT", type=i32, expr=IntLiteral(7)),
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "# global variable global_counter: Int32 (manual binding required)" in out
    assert 'comptime LIB_NAME = "bindgen"' in out
    assert "comptime LIMIT = Int32(7)" in out
