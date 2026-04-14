"""Focused IR and codegen tests for newer parser/model features."""

from __future__ import annotations

from mojo_bindgen.codegen.analysis import analyze_unit
from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.lowering import lower_type
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    BinaryExpr,
    Const,
    GlobalVar,
    IntLiteral,
    MacroDecl,
    NullPtrLiteral,
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


def test_generator_renders_global_var_stub_and_macro_comments() -> None:
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
            Const(
                name="FLAGS",
                type=i32,
                expr=BinaryExpr(op="|", lhs=IntLiteral(1), rhs=IntLiteral(2)),
            ),
            MacroDecl(
                name="MACRO_OK",
                tokens=["1u"],
                kind="object_like_supported",
                expr=IntLiteral(1),
                type=i32,
            ),
            MacroDecl(
                name="MACRO_FILE",
                tokens=["__FILE__"],
                kind="predefined",
                diagnostic="predefined macro preserved without evaluation",
            ),
            MacroDecl(
                name="MACRO_NULL",
                tokens=["(", "void", "*", ")", "0"],
                kind="object_like_supported",
                expr=NullPtrLiteral(),
                type=Primitive(name="void", kind=PrimitiveKind.VOID, is_signed=False, size_bytes=0),
            ),
            MacroDecl(
                name="MACRO_GENERIC",
                tokens=["_Generic", "(", "0", ",", "int", ":", "42", ",", "default", ":", "0", ")"],
                kind="object_like_unsupported",
                diagnostic="unsupported macro replacement list",
            ),
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "# global variable global_counter: Int32 (manual binding required)" in out
    assert 'comptime LIB_NAME = "bindgen"' in out
    assert "comptime LIMIT = Int32(7)" in out
    assert "comptime FLAGS = (Int32(1) | Int32(2))" in out
    assert "comptime MACRO_OK = Int32(1)" in out
    assert "# macro MACRO_FILE: predefined macro preserved without evaluation" in out
    assert "# define MACRO_FILE __FILE__" in out
    assert "# macro MACRO_NULL: null pointer macro is not emitted directly" in out
    assert "# define MACRO_NULL ( void * ) 0" in out
    assert "# macro MACRO_GENERIC: unsupported macro replacement list" in out
