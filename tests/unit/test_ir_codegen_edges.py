"""Focused IR and codegen tests for newer parser/model features."""

from __future__ import annotations

from mojo_bindgen.codegen.analysis import analyze_unit
from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.lowering import lower_type
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    BinaryExpr,
    Const,
    Field,
    FloatKind,
    FloatType,
    Function,
    FunctionPtr,
    GlobalVar,
    IntKind,
    IntType,
    IntLiteral,
    MacroDecl,
    NullPtrLiteral,
    OpaqueRecordRef,
    Param,
    Pointer,
    QualifiedType,
    Qualifiers,
    RefExpr,
    StringLiteral,
    Struct,
    StructRef,
    TypeRef,
    Typedef,
    Unit,
    UnsupportedType,
    VoidType,
)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _char() -> IntType:
    return IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1)


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
                type=_char(),
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
                type=VoidType(),
            ),
            MacroDecl(
                name="MACRO_GENERIC",
                tokens=["_Generic", "(", "0", ",", "int", ":", "42", ",", "default", ":", "0", ")"],
                kind="object_like_unsupported",
                diagnostic="unsupported macro replacement list",
            ),
            MacroDecl(
                name="MACRO_REF",
                tokens=["MACRO_OK"],
                kind="object_like_supported",
                expr=RefExpr("MACRO_OK"),
                type=i32,
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
    assert (
        "# macro MACRO_REF: identifier reference macro is not emitted directly; "
        "only literal macros are currently supported"
    ) in out
    assert "# define MACRO_REF MACRO_OK" in out


def test_generator_emits_macro_and_const_before_global_and_function_sections() -> None:
    i32 = _i32()
    fn = Function(
        decl_id="fn:do_work",
        name="do_work",
        link_name="do_work",
        ret=i32,
        params=[],
        is_variadic=False,
    )
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
            fn,
            MacroDecl(
                name="MACRO_OK",
                tokens=["1"],
                kind="object_like_supported",
                expr=IntLiteral(1),
                type=i32,
            ),
            Const(name="LIMIT", type=i32, expr=IntLiteral(7)),
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    macro_pos = out.index("comptime MACRO_OK = Int32(1)")
    const_pos = out.index("comptime LIMIT = Int32(7)")
    global_pos = out.index("# global variable global_counter: Int32 (manual binding required)")
    fn_pos = out.index('def do_work() abi("C") -> Int32:')
    assert macro_pos < global_pos
    assert const_pos < global_pos
    assert macro_pos < fn_pos
    assert const_pos < fn_pos


def test_generator_preserves_typedef_names_in_fields_globals_and_aliases() -> None:
    i32 = _i32()
    my_uint = Typedef(decl_id="typedef:my_uint", name="my_uint", aliased=i32, canonical=i32)
    my_uint_ref = TypeRef(decl_id=my_uint.decl_id, name="my_uint", canonical=i32)
    my_uint_ptr = Typedef(
        decl_id="typedef:my_uint_ptr",
        name="my_uint_ptr",
        aliased=Pointer(pointee=my_uint_ref),
        canonical=Pointer(pointee=i32),
    )
    my_uint_ptr_ref = TypeRef(
        decl_id=my_uint_ptr.decl_id,
        name="my_uint_ptr",
        canonical=Pointer(pointee=i32),
    )
    holder = Struct(
        decl_id="struct:holder",
        name="holder",
        c_name="holder",
        fields=[
            Field(name="value", source_name="value", type=my_uint_ref, byte_offset=0),
            Field(name="ptr", source_name="ptr", type=my_uint_ptr_ref, byte_offset=8),
        ],
        size_bytes=16,
        align_bytes=8,
        is_union=False,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            my_uint,
            my_uint_ptr,
            holder,
            GlobalVar(
                decl_id="var:global_ptr",
                name="global_ptr",
                link_name="global_ptr",
                type=my_uint_ptr_ref,
            ),
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "comptime my_uint = Int32" in out
    assert "comptime my_uint_ptr = UnsafePointer[my_uint, MutExternalOrigin]" in out
    assert "var value: my_uint" in out
    assert "var ptr: my_uint_ptr" in out
    assert "# global variable global_ptr: my_uint_ptr (manual binding required)" in out


def test_generator_emits_function_pointer_return_wrappers_for_both_link_modes() -> None:
    i32 = _i32()
    fp = FunctionPtr(ret=i32, params=[i32, i32], param_names=["a", "b"], is_variadic=False)
    fp_typedef = Typedef(
        decl_id="typedef:pfr_binary_op_t",
        name="pfr_binary_op_t",
        aliased=fp,
        canonical=fp,
    )
    fp_typedef_ref = TypeRef(
        decl_id=fp_typedef.decl_id,
        name="pfr_binary_op_t",
        canonical=fp,
    )
    choose = Function(
        decl_id="fn:pfr_select_add",
        name="pfr_select_add",
        link_name="pfr_select_add",
        ret=fp_typedef_ref,
        params=[],
        is_variadic=False,
    )
    choose_direct = Function(
        decl_id="fn:pfr_select_add_direct",
        name="pfr_select_add_direct",
        link_name="pfr_select_add_direct",
        ret=fp,
        params=[],
        is_variadic=False,
    )
    call = Function(
        decl_id="fn:pfr_call",
        name="pfr_call",
        link_name="pfr_call",
        ret=i32,
        params=[
            Param(name="op", type=fp_typedef_ref),
            Param(name="lhs", type=i32),
            Param(name="rhs", type=i32),
        ],
        is_variadic=False,
    )
    unit = Unit(
        source_header="t.h",
        library="pfr",
        link_name="pfr",
        decls=[fp_typedef, choose, choose_direct, call],
    )

    external_out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert 'comptime pfr_binary_op_t = def (a: Int32, b: Int32) abi("C") -> Int32' in external_out
    assert 'def pfr_select_add() abi("C") -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:' in external_out
    assert (
        'def pfr_select_add_direct() abi("C") -> '
        'UnsafePointer[pfr_select_add_direct_return_cb, MutExternalOrigin]:'
    ) in external_out
    assert (
        'return external_call["pfr_select_add", UnsafePointer[pfr_binary_op_t, MutExternalOrigin]]()'
        in external_out
    )
    assert (
        'return external_call["pfr_select_add_direct", '
        'UnsafePointer[pfr_select_add_direct_return_cb, MutExternalOrigin]]()'
        in external_out
    )
    assert (
        'def pfr_call(op: UnsafePointer[pfr_binary_op_t, MutExternalOrigin], lhs: Int32, rhs: Int32) abi("C") -> Int32:'
        in external_out
    )
    assert (
        'return external_call["pfr_call", Int32, UnsafePointer[pfr_binary_op_t, MutExternalOrigin], Int32, Int32](op, lhs, rhs)'
        in external_out
    )

    dl_out = MojoGenerator(
        MojoEmitOptions(
            linking="owned_dl_handle",
            library_path_hint="/tmp/libpfr.so",
        )
    ).generate(unit)
    assert 'comptime pfr_binary_op_t = def (a: Int32, b: Int32) abi("C") -> Int32' in dl_out
    assert "def pfr_select_add() raises -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:" in dl_out
    assert (
        "def pfr_select_add_direct() raises -> "
        "UnsafePointer[pfr_select_add_direct_return_cb, MutExternalOrigin]:"
    ) in dl_out
    assert (
        'return _bindgen_dl().call["pfr_select_add", UnsafePointer[pfr_binary_op_t, MutExternalOrigin]]()'
        in dl_out
    )
    assert (
        'return _bindgen_dl().call["pfr_select_add_direct", '
        'UnsafePointer[pfr_select_add_direct_return_cb, MutExternalOrigin]]()'
        in dl_out
    )
    assert (
        'return _bindgen_dl().call["pfr_call", Int32, UnsafePointer[pfr_binary_op_t, MutExternalOrigin], Int32, Int32](op, lhs, rhs)'
        in dl_out
    )


def test_generator_emits_struct_field_callback_aliases() -> None:
    i32 = _i32()
    sqlite3 = Struct(
        decl_id="struct:sqlite3",
        name="sqlite3",
        c_name="sqlite3",
        fields=[],
        size_bytes=0,
        align_bytes=8,
        is_complete=False,
    )
    vtab = Struct(
        decl_id="struct:sqlite3_vtab",
        name="sqlite3_vtab",
        c_name="sqlite3_vtab",
        fields=[],
        size_bytes=0,
        align_bytes=8,
        is_complete=False,
    )
    sqlite3_ref = Pointer(
        pointee=StructRef(
            decl_id="struct:sqlite3",
            name="sqlite3",
            c_name="sqlite3",
            size_bytes=0,
        )
    )
    vtab_out = Pointer(
        pointee=Pointer(
            pointee=StructRef(
                decl_id="struct:sqlite3_vtab",
                name="sqlite3_vtab",
                c_name="sqlite3_vtab",
                size_bytes=0,
            )
        )
    )
    argv = Pointer(pointee=Pointer(pointee=_char()))
    err = Pointer(pointee=Pointer(pointee=_char()))
    cb = FunctionPtr(
        ret=i32,
        params=[sqlite3_ref, Pointer(pointee=None), i32, argv, vtab_out, err],
        param_names=["db", "pAux", "argc", "argv", "ppVTab", "errmsg_out"],
        is_variadic=False,
    )
    module = Struct(
        decl_id="struct:sqlite3_module",
        name="sqlite3_module",
        c_name="sqlite3_module",
        fields=[
            Field(name="iVersion", source_name="iVersion", type=i32, byte_offset=0),
            Field(name="xCreate", source_name="xCreate", type=cb, byte_offset=8),
            Field(name="xConnect", source_name="xConnect", type=cb, byte_offset=16),
        ],
        size_bytes=24,
        align_bytes=8,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="sqlite", link_name="sqlite", decls=[sqlite3, vtab, module])
    )
    assert "comptime sqlite3_module_xCreate_cb = def (" in out
    assert "comptime sqlite3_module_xConnect_cb = def (" in out
    assert "var xCreate: UnsafePointer[sqlite3_module_xCreate_cb, MutExternalOrigin]" in out
    assert "var xConnect: UnsafePointer[sqlite3_module_xConnect_cb, MutExternalOrigin]" in out
    assert "# function pointer (fixed):" not in out


def test_generator_uses_callback_alias_types_in_wrapper_abi_lists() -> None:
    i32 = _i32()
    opaque = Pointer(pointee=None)
    cmp_cb = FunctionPtr(
        ret=i32,
        params=[opaque, i32, Pointer(pointee=None), i32, Pointer(pointee=None)],
        param_names=["ctx", "lhs_len", "lhs", "rhs_len", "rhs"],
        is_variadic=False,
    )
    destroy_cb = FunctionPtr(
        ret=VoidType(),
        params=[opaque],
        param_names=["ctx"],
        is_variadic=False,
    )
    db = Pointer(
        pointee=StructRef(
            decl_id="struct:sqlite3",
            name="sqlite3",
            c_name="sqlite3",
            size_bytes=0,
        )
    )
    create = Function(
        decl_id="fn:sqlite3_create_collation_v2",
        name="sqlite3_create_collation_v2",
        link_name="sqlite3_create_collation_v2",
        ret=i32,
        params=[
            Param(name="db", type=db),
            Param(name="zName", type=Pointer(pointee=_char())),
            Param(name="eTextRep", type=i32),
            Param(name="ctx", type=opaque),
            Param(name="xCompare", type=cmp_cb),
            Param(name="xDestroy", type=destroy_cb),
        ],
        is_variadic=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(
            source_header="t.h",
            library="sqlite",
            link_name="sqlite",
            decls=[
                Struct(
                    decl_id="struct:sqlite3",
                    name="sqlite3",
                    c_name="sqlite3",
                    fields=[],
                    size_bytes=0,
                    align_bytes=8,
                    is_complete=False,
                ),
                create,
            ],
        )
    )
    assert "comptime sqlite3_create_collation_v2_xCompare_cb = def (" in out
    assert "comptime sqlite3_create_collation_v2_xDestroy_cb = def (" in out
    assert (
        "def sqlite3_create_collation_v2("
        "db: UnsafePointer[sqlite3, MutExternalOrigin], "
        "zName: UnsafePointer[Int8, MutExternalOrigin], "
        "eTextRep: Int32, "
        "ctx: MutOpaquePointer[MutExternalOrigin], "
        "xCompare: UnsafePointer[sqlite3_create_collation_v2_xCompare_cb, MutExternalOrigin], "
        "xDestroy: UnsafePointer[sqlite3_create_collation_v2_xDestroy_cb, MutExternalOrigin]"
        ') abi("C") -> Int32:'
    ) in out
    assert (
        'return external_call["sqlite3_create_collation_v2", Int32, '
        'UnsafePointer[sqlite3, MutExternalOrigin], '
        'UnsafePointer[Int8, MutExternalOrigin], Int32, MutOpaquePointer[MutExternalOrigin], '
        'UnsafePointer[sqlite3_create_collation_v2_xCompare_cb, MutExternalOrigin], '
        'UnsafePointer[sqlite3_create_collation_v2_xDestroy_cb, MutExternalOrigin]]'
        "(db, zName, eTextRep, ctx, xCompare, xDestroy)"
    ) in out
