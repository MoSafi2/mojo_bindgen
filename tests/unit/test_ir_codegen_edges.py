"""Focused IR and codegen tests for newer parser/model features."""

from __future__ import annotations

from mojo_bindgen.analysis.analyze_for_mojo import analyze_unit
from mojo_bindgen.codegen.generator import MojoGenerator
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import map_type
from mojo_bindgen.ir import (
    AtomicType,
    BinaryExpr,
    CastExpr,
    ComplexType,
    Const,
    Field,
    FloatKind,
    FloatLiteral,
    FloatType,
    Function,
    FunctionPtr,
    GlobalVar,
    IntKind,
    IntLiteral,
    IntType,
    MacroDecl,
    NullPtrLiteral,
    OpaqueRecordRef,
    Param,
    Pointer,
    RefExpr,
    StringLiteral,
    Struct,
    StructRef,
    Typedef,
    TypeRef,
    Unit,
    UnsupportedType,
    VectorType,
    VoidType,
)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _char() -> IntType:
    return IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1)


def _u32() -> IntType:
    return IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)


def _bool() -> IntType:
    return IntType(int_kind=IntKind.BOOL, size_bytes=1, align_bytes=1)


def test_generator_emits_integer_cast_macro_as_single_scalar_call() -> None:
    """``(size_t)-1`` style macros emit as one scalar constructor, not binary minus."""
    size_t_like = IntType(int_kind=IntKind.ULONG, size_bytes=8, align_bytes=8)
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            MacroDecl(
                name="CURL_ZERO_TERMINATED",
                tokens=["(", "(", "size_t", ")", "-", "1", ")"],
                kind="object_like_supported",
                expr=CastExpr(target=size_t_like, expr=IntLiteral(-1)),
                type=size_t_like,
            ),
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "comptime CURL_ZERO_TERMINATED = c_ulong(-1)" in out


def test_map_opaque_record_ref_as_opaque_pointer() -> None:
    t = OpaqueRecordRef(decl_id="struct:FILE", name="FILE", c_name="FILE")
    assert map_type(t, ffi_origin="external") == "MutOpaquePointer[MutExternalOrigin]"


def test_map_unsupported_type_with_size_becomes_inline_bytes() -> None:
    t = UnsupportedType(
        category="unsupported_extension",
        spelling="mystery_t",
        reason="not modeled",
        size_bytes=16,
    )
    assert map_type(t, ffi_origin="external") == "InlineArray[UInt8, 16]"


def test_incomplete_struct_emitted_as_opaque_stub_not_as_layout_struct() -> None:
    st = Struct(
        decl_id="struct:foo",
        name="foo",
        c_name="foo",
        fields=[],
        size_bytes=0,
        align_bytes=0,
        is_complete=False,
    )
    au = analyze_unit(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st]),
        MojoEmitOptions(),
    )
    assert au.ordered_structs == ()
    assert len(au.ordered_incomplete_structs) == 1
    assert au.ordered_incomplete_structs[0].decl.decl_id == st.decl_id


def test_generator_emits_pure_bitfield_struct_as_storage_plus_accessors() -> None:
    u32 = _u32()
    b = _bool()
    st = Struct(
        decl_id="struct:Bits",
        name="Bits",
        c_name="Bits",
        fields=[
            Field(
                name="ready",
                source_name="ready",
                type=u32,
                byte_offset=0,
                is_bitfield=True,
                bit_offset=0,
                bit_width=1,
            ),
            Field(
                name="state",
                source_name="state",
                type=u32,
                byte_offset=0,
                is_bitfield=True,
                bit_offset=1,
                bit_width=3,
            ),
            Field(
                name="",
                source_name="",
                type=u32,
                byte_offset=4,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=32,
                bit_width=0,
            ),
            Field(
                name="enabled",
                source_name="enabled",
                type=b,
                byte_offset=4,
                is_bitfield=True,
                bit_offset=32,
                bit_width=1,
            ),
        ],
        size_bytes=8,
        align_bytes=4,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    )
    assert "@fieldwise_init\nstruct Bits" not in out
    assert "var __bf0: c_uint" in out
    assert "var __bf1: c_uchar" in out
    assert "var __bf2:" not in out
    assert "var ready: c_uint" not in out
    assert "def __init__(out self):" in out
    assert "def __init__(out self, ready: c_uint, state: c_uint, enabled: Bool):" in out
    assert "self.__bf0 = c_uint(0)" in out
    assert "self.__bf1 = c_uchar(0)" in out
    assert "self.set_ready(ready)" in out
    assert "self.set_state(state)" in out
    assert "self.set_enabled(enabled)" in out
    assert "def ready(self) -> c_uint:" in out
    assert "def set_ready(mut self, value: c_uint):" in out
    assert "def enabled(self) -> Bool:" in out
    assert "def set_enabled(mut self, value: Bool):" in out


def test_generator_emits_mixed_struct_bitfields_as_storage_plus_accessors() -> None:
    u32 = _u32()
    st = Struct(
        decl_id="struct:MixedBits",
        name="MixedBits",
        c_name="MixedBits",
        fields=[
            Field(name="tag", source_name="tag", type=u32, byte_offset=0),
            Field(
                name="ready",
                source_name="ready",
                type=u32,
                byte_offset=4,
                is_bitfield=True,
                bit_offset=32,
                bit_width=1,
            ),
        ],
        size_bytes=8,
        align_bytes=4,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    )
    assert "@fieldwise_init\nstruct MixedBits" in out
    assert "var tag: c_uint" in out
    assert "var ready: c_uint" not in out
    assert "var __bf0: c_uint" in out
    assert "def __init__(out self" not in out
    assert "def ready(self) -> c_uint:" in out
    assert "def set_ready(mut self, value: c_uint):" in out


def test_generator_resets_bitfield_storage_after_zero_width_boundary_in_mixed_struct() -> None:
    u32 = _u32()
    st = Struct(
        decl_id="struct:ZeroWidthMixed",
        name="ZeroWidthMixed",
        c_name="ZeroWidthMixed",
        fields=[
            Field(name="tag", source_name="tag", type=u32, byte_offset=0),
            Field(
                name="left",
                source_name="left",
                type=u32,
                byte_offset=4,
                is_bitfield=True,
                bit_offset=32,
                bit_width=1,
            ),
            Field(
                name="",
                source_name="",
                type=u32,
                byte_offset=4,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=63,
                bit_width=0,
            ),
            Field(
                name="right",
                source_name="right",
                type=u32,
                byte_offset=8,
                is_bitfield=True,
                bit_offset=64,
                bit_width=1,
            ),
        ],
        size_bytes=12,
        align_bytes=4,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    )
    assert "var __bf0: c_uint" in out
    assert "var __bf1: c_uint" in out
    assert "def left(self) -> c_uint:" in out
    assert "def right(self) -> c_uint:" in out


def test_generator_emits_zero_init_only_for_anonymous_only_pure_bitfield_struct() -> None:
    u32 = _u32()
    st = Struct(
        decl_id="struct:OnlyAnonBits",
        name="OnlyAnonBits",
        c_name="OnlyAnonBits",
        fields=[
            Field(
                name="",
                source_name="",
                type=u32,
                byte_offset=0,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=0,
                bit_width=8,
            ),
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    )
    assert "@fieldwise_init\nstruct OnlyAnonBits" not in out
    assert "def __init__(out self):" in out
    assert "def __init__(out self," not in out


def test_generator_omits_self_alias_typedef_for_complete_union_name() -> None:
    i32 = _i32()
    union_decl = Struct(
        decl_id="union:U",
        name="U",
        c_name="union U",
        fields=[
            Field(name="a", source_name="a", type=i32, byte_offset=0),
            Field(name="b", source_name="b", type=_u32(), byte_offset=0),
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=True,
    )
    union_ref = StructRef(
        decl_id=union_decl.decl_id,
        name=union_decl.name,
        c_name=union_decl.c_name,
        is_union=True,
        size_bytes=union_decl.size_bytes,
    )
    td = Typedef(decl_id="typedef:U", name="U", aliased=union_ref, canonical=union_ref)
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[union_decl, td])
    )
    assert "comptime U = UnsafeUnion[c_int, c_uint]" in out
    assert out.count("comptime U =") == 1


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
                tokens=[
                    "_Generic",
                    "(",
                    "0",
                    ",",
                    "int",
                    ":",
                    "42",
                    ",",
                    "default",
                    ":",
                    "0",
                    ")",
                ],
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
    import_line = [ln for ln in out.splitlines() if ln.startswith("from std.ffi import")][0]
    assert (
        "external_call" in import_line and "OwnedDLHandle" in import_line and "c_int" in import_line
    )
    assert "def _bindgen_dl() raises -> OwnedDLHandle:" in out
    assert "struct GlobalVar[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:" in out
    assert (
        "struct GlobalConst[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:" in out
    )
    assert 'comptime global_counter = GlobalVar[T=c_int, link="global_counter"]' in out
    assert 'comptime LIB_NAME = "bindgen"' in out
    assert "comptime LIMIT = c_int(7)" in out
    assert "comptime FLAGS = (c_int(1) | c_int(2))" in out
    assert "comptime MACRO_OK = c_int(1)" in out
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
    macro_pos = out.index("comptime MACRO_OK = c_int(1)")
    const_pos = out.index("comptime LIMIT = c_int(7)")
    global_pos = out.index('comptime global_counter = GlobalVar[T=c_int, link="global_counter"]')
    fn_pos = out.index('def do_work() abi("C") -> c_int:')
    assert macro_pos < global_pos
    assert const_pos < global_pos
    assert macro_pos < fn_pos
    assert const_pos < fn_pos


def test_generator_strips_c_float_suffix_in_macro_and_const() -> None:
    f32 = FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4)
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            MacroDecl(
                name="PRIO_LOW",
                tokens=["0.25", "f"],
                kind="object_like_supported",
                expr=FloatLiteral("0.25f"),
                type=f32,
            ),
            Const(name="PRIO_HIGH", type=f32, expr=FloatLiteral("0.75F")),
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "comptime PRIO_LOW = 0.25" in out
    assert "0.25f" not in out
    assert "comptime PRIO_HIGH = 0.75" in out
    assert "0.75F" not in out


def test_generator_imports_simd_complex_atomic_and_emits_fallback_notes() -> None:
    f32 = FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4)
    wchar = IntType(int_kind=IntKind.WCHAR, size_bytes=4, align_bytes=4)
    st = Struct(
        decl_id="struct:simd_holder",
        name="simd_holder",
        c_name="simd_holder",
        fields=[
            Field(
                name="lanes",
                source_name="lanes",
                type=VectorType(element=f32, count=4, size_bytes=16),
                byte_offset=0,
            ),
            Field(
                name="complex_value",
                source_name="complex_value",
                type=ComplexType(element=f32, size_bytes=8),
                byte_offset=16,
            ),
            Field(
                name="fallback_atomic",
                source_name="fallback_atomic",
                type=AtomicType(value_type=wchar),
                byte_offset=24,
            ),
        ],
        size_bytes=32,
        align_bytes=16,
        is_union=False,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "from std.builtin.simd import SIMD" in out
    assert "from std.complex import ComplexSIMD" in out
    assert "from std.os import Atomic" not in out
    assert "var lanes: SIMD[DType.float32, 4]" in out
    assert "var complex_value: ComplexSIMD[DType.float32, 1]" in out
    assert "var fallback_atomic: Int32" in out
    assert "atomic types were mapped to their underlying non-atomic Mojo type" in out


def test_generator_imports_atomic_for_representable_atomic_types() -> None:
    i32 = _i32()
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            GlobalVar(
                decl_id="var:counter",
                name="counter",
                link_name="counter",
                type=AtomicType(value_type=i32),
            )
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert "from std.atomic import Atomic" in out
    assert (
        "# global variable counter: Atomic[DType.int32] (atomic global requires manual "
        "binding (use Atomic APIs on a pointer))" in out
    )


def test_generator_omits_copy_traits_and_fieldwise_init_for_atomic_struct_fields() -> None:
    i32 = _i32()
    u32 = _u32()
    atomic_holder = Struct(
        decl_id="struct:AtomicHolder",
        name="AtomicHolder",
        c_name="AtomicHolder",
        fields=[
            Field(
                name="counter",
                source_name="counter",
                type=AtomicType(value_type=i32),
                byte_offset=0,
            ),
            Field(
                name="flags",
                source_name="flags",
                type=AtomicType(value_type=u32),
                byte_offset=4,
            ),
            Field(
                name="user",
                source_name="user",
                type=Pointer(pointee=None),
                byte_offset=8,
            ),
        ],
        size_bytes=16,
        align_bytes=8,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[atomic_holder])
    )
    assert "@fieldwise_init\nstruct AtomicHolder" not in out
    assert "struct AtomicHolder(Copyable" not in out
    assert "struct AtomicHolder(Movable" not in out
    assert "struct AtomicHolder:" in out
    assert "var counter: Atomic[DType.int32]" in out
    assert "var flags: Atomic[DType.uint32]" in out


def test_generator_emits_global_const_wrapper_for_const_qualified_scalar() -> None:
    i32 = _i32()
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            GlobalVar(
                decl_id="var:limit",
                name="limit",
                link_name="limit",
                type=i32,
                is_const=True,
            ),
        ],
    )
    out = MojoGenerator(MojoEmitOptions()).generate(unit)
    assert 'comptime limit = GlobalConst[T=c_int, link="limit"]' in out


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
    assert "comptime my_uint = c_int" in out
    assert "comptime my_uint_ptr = UnsafePointer[my_uint, MutExternalOrigin]" in out
    assert "var value: my_uint" in out
    assert "var ptr: my_uint_ptr" in out
    assert 'comptime global_ptr = GlobalVar[T=my_uint_ptr, link="global_ptr"]' in out


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
    assert (
        'comptime pfr_binary_op_t = def (a: c_int, b: c_int) thin abi("C") -> c_int' in external_out
    )
    assert (
        'def pfr_select_add() abi("C") -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:'
        in external_out
    )
    assert (
        'def pfr_select_add_direct() abi("C") -> '
        "UnsafePointer[pfr_select_add_direct_return_cb, MutExternalOrigin]:"
    ) in external_out
    assert (
        'return external_call["pfr_select_add", UnsafePointer[pfr_binary_op_t, MutExternalOrigin]]()'
        in external_out
    )
    assert (
        'return external_call["pfr_select_add_direct", '
        "UnsafePointer[pfr_select_add_direct_return_cb, MutExternalOrigin]]()" in external_out
    )
    assert (
        'def pfr_call(op: UnsafePointer[pfr_binary_op_t, MutExternalOrigin], lhs: c_int, rhs: c_int) abi("C") -> c_int:'
        in external_out
    )
    assert (
        'return external_call["pfr_call", c_int, UnsafePointer[pfr_binary_op_t, MutExternalOrigin], c_int, c_int](op, lhs, rhs)'
        in external_out
    )

    dl_out = MojoGenerator(
        MojoEmitOptions(
            linking="owned_dl_handle",
            library_path_hint="/tmp/libpfr.so",
        )
    ).generate(unit)
    assert 'comptime pfr_binary_op_t = def (a: c_int, b: c_int) thin abi("C") -> c_int' in dl_out
    assert (
        "def pfr_select_add() raises -> UnsafePointer[pfr_binary_op_t, MutExternalOrigin]:"
        in dl_out
    )
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
        "UnsafePointer[pfr_select_add_direct_return_cb, MutExternalOrigin]]()" in dl_out
    )
    assert (
        'return _bindgen_dl().call["pfr_call", c_int, UnsafePointer[pfr_binary_op_t, MutExternalOrigin], c_int, c_int](op, lhs, rhs)'
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
        Unit(
            source_header="t.h",
            library="sqlite",
            link_name="sqlite",
            decls=[sqlite3, vtab, module],
        )
    )
    assert "comptime sqlite3_module_xCreate_cb = def (" in out
    assert "comptime sqlite3_module_xConnect_cb = def (" in out
    assert "var xCreate: UnsafePointer[sqlite3_module_xCreate_cb, MutExternalOrigin]" in out
    assert "var xConnect: UnsafePointer[sqlite3_module_xConnect_cb, MutExternalOrigin]" in out
    assert "# function pointer (fixed):" not in out


def test_generator_emits_nominal_union_alias_for_struct_arm_union() -> None:
    i32 = _i32()
    parts = Struct(
        decl_id="struct:Parts",
        name="Parts",
        c_name="Parts",
        fields=[
            Field(name="lo", source_name="lo", type=i32, byte_offset=0),
            Field(name="hi", source_name="hi", type=i32, byte_offset=4),
        ],
        size_bytes=8,
        align_bytes=4,
        is_union=False,
    )
    payload = Struct(
        decl_id="union:Payload",
        name="Payload",
        c_name="Payload",
        fields=[
            Field(name="raw", source_name="raw", type=i32, byte_offset=0),
            Field(
                name="parts",
                source_name="parts",
                type=StructRef(
                    decl_id=parts.decl_id,
                    name=parts.name,
                    c_name=parts.c_name,
                    size_bytes=parts.size_bytes,
                    is_union=False,
                ),
                byte_offset=0,
            ),
        ],
        size_bytes=8,
        align_bytes=4,
        is_union=True,
    )
    holder = Struct(
        decl_id="struct:Holder",
        name="Holder",
        c_name="Holder",
        fields=[
            Field(
                name="payload",
                source_name="payload",
                type=StructRef(
                    decl_id=payload.decl_id,
                    name=payload.name,
                    c_name=payload.c_name,
                    size_bytes=payload.size_bytes,
                    is_union=True,
                ),
                byte_offset=0,
            )
        ],
        size_bytes=8,
        align_bytes=4,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[parts, payload, holder])
    )
    assert "comptime Payload = UnsafeUnion[c_int, Parts]" in out
    assert "var payload: Payload" in out


def test_generator_emits_documented_inline_array_fallback_for_ineligible_union() -> None:
    i32 = _i32()
    union_decl = Struct(
        decl_id="union:Dup",
        name="Dup",
        c_name="Dup",
        fields=[
            Field(name="a", source_name="a", type=i32, byte_offset=0),
            Field(name="b", source_name="b", type=i32, byte_offset=0),
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=True,
    )
    holder = Struct(
        decl_id="struct:HolderDup",
        name="HolderDup",
        c_name="HolderDup",
        fields=[
            Field(
                name="payload",
                source_name="payload",
                type=StructRef(
                    decl_id=union_decl.decl_id,
                    name=union_decl.name,
                    c_name=union_decl.c_name,
                    size_bytes=union_decl.size_bytes,
                    is_union=True,
                ),
                byte_offset=0,
            )
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[union_decl, holder])
    )
    assert "comptime Dup = InlineArray[UInt8, 4]" in out
    assert "lowered as InlineArray[UInt8, 4] to preserve layout" in out
    assert "var payload: Dup" in out


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
        "zName: UnsafePointer[c_char, MutExternalOrigin], "
        "eTextRep: c_int, "
        "ctx: MutOpaquePointer[MutExternalOrigin], "
        "xCompare: UnsafePointer[sqlite3_create_collation_v2_xCompare_cb, MutExternalOrigin], "
        "xDestroy: UnsafePointer[sqlite3_create_collation_v2_xDestroy_cb, MutExternalOrigin]"
        ') abi("C") -> c_int:'
    ) in out
    assert (
        'return external_call["sqlite3_create_collation_v2", c_int, '
        "UnsafePointer[sqlite3, MutExternalOrigin], "
        "UnsafePointer[c_char, MutExternalOrigin], c_int, MutOpaquePointer[MutExternalOrigin], "
        "UnsafePointer[sqlite3_create_collation_v2_xCompare_cb, MutExternalOrigin], "
        "UnsafePointer[sqlite3_create_collation_v2_xDestroy_cb, MutExternalOrigin]]"
        "(db, zName, eTextRep, ctx, xCompare, xDestroy)"
    ) in out


def test_generator_keeps_nested_callback_typedef_in_wrapper_abi_lists() -> None:
    cb_sig = FunctionPtr(
        ret=Pointer(pointee=None),
        params=[Pointer(pointee=None), _i32()],
        param_names=["ctx", "value"],
        is_variadic=False,
    )
    cb_typedef = Typedef(
        decl_id="typedef:nested_cb_t",
        name="nested_cb_t",
        aliased=cb_sig,
        canonical=cb_sig,
    )
    fn = Function(
        decl_id="fn:install_nested_cb",
        name="install_nested_cb",
        link_name="install_nested_cb",
        ret=VoidType(),
        params=[
            Param(
                name="slot",
                type=Pointer(
                    pointee=Pointer(
                        pointee=TypeRef(
                            decl_id=cb_typedef.decl_id,
                            name=cb_typedef.name,
                            canonical=cb_typedef.canonical,
                        )
                    )
                ),
            )
        ],
        is_variadic=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[cb_typedef, fn])
    )
    assert "comptime nested_cb_t = def (" in out
    assert (
        "def install_nested_cb(slot: UnsafePointer[UnsafePointer[UnsafePointer[nested_cb_t, MutExternalOrigin], "
        'MutExternalOrigin], MutExternalOrigin]) abi("C") -> None:'
    ) in out
    assert (
        'external_call["install_nested_cb", NoneType, '
        "UnsafePointer[UnsafePointer[UnsafePointer[nested_cb_t, MutExternalOrigin], MutExternalOrigin], MutExternalOrigin]](slot)"
    ) in out


def test_generator_emits_std_ffi_c_aliases_and_imports_by_default() -> None:
    i32 = _i32()
    fn = Function(
        decl_id="fn:sf_add",
        name="sf_add",
        link_name="sf_add",
        ret=i32,
        params=[
            Param(name="a", type=i32),
            Param(name="b", type=i32),
        ],
        is_variadic=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(source_header="t.h", library="t", link_name="t", decls=[fn])
    )
    assert "from std.ffi import external_call, c_int" in out
    assert 'def sf_add(a: c_int, b: c_int) abi("C") -> c_int:' in out
    assert 'return external_call["sf_add", c_int, c_int, c_int](a, b)' in out


def test_generator_imports_std_ffi_scalars_used_only_in_callback_signatures() -> None:
    """Scalars inside FunctionPtr surfaces must appear in ``from std.ffi import`` even when
    ``canonical`` on decl types never visits those scalars (e.g. ret-only function + typedef FP).
    """
    i32 = _i32()
    fp = FunctionPtr(
        ret=i32,
        params=[i32, i32],
        param_names=["a", "b"],
        is_variadic=False,
    )
    fp_typedef = Typedef(
        decl_id="typedef:only_cb_t",
        name="only_cb_t",
        aliased=fp,
        canonical=fp,
    )
    fp_typedef_ref = TypeRef(
        decl_id=fp_typedef.decl_id,
        name="only_cb_t",
        canonical=fp,
    )
    getter = Function(
        decl_id="fn:get_only_cb",
        name="get_only_cb",
        link_name="get_only_cb",
        ret=fp_typedef_ref,
        params=[],
        is_variadic=False,
    )
    out = MojoGenerator(MojoEmitOptions()).generate(
        Unit(
            source_header="t.h",
            library="t",
            link_name="t",
            decls=[fp_typedef, getter],
        )
    )
    assert "from std.ffi import external_call, c_int" in out
    assert 'comptime only_cb_t = def (a: c_int, b: c_int) thin abi("C") -> c_int' in out
    assert 'def get_only_cb() abi("C") -> UnsafePointer[only_cb_t, MutExternalOrigin]:' in out
