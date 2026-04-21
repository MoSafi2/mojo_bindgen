"""Unit tests for :mod:`mojo_bindgen.passes.analyze_for_mojo` (no libclang)."""

from __future__ import annotations

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    ComplexType,
    Field,
    FloatKind,
    FloatType,
    Function,
    FunctionPtr,
    IntKind,
    IntType,
    Param,
    Struct,
    StructRef,
    Typedef,
    TypeRef,
    Unit,
    VectorType,
    VoidType,
)
from mojo_bindgen.passes.analyze_for_mojo import AnalyzedFunction, analyze_unit


def _f32() -> FloatType:
    return FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u32() -> IntType:
    return IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)


def _bool() -> IntType:
    return IntType(int_kind=IntKind.BOOL, size_bytes=1, align_bytes=1)


def test_analyze_variadic_function_kind() -> None:
    v = VoidType()
    fn = Function(
        decl_id="fn:vf",
        name="vf",
        link_name="vf",
        ret=v,
        params=[],
        is_variadic=True,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[fn])
    au = analyze_unit(unit, MojoEmitOptions())
    assert len(au.tail_decls) == 1
    f = au.tail_decls[0]
    assert f.kind == "variadic_stub"


def test_analyze_non_register_struct_return_kind() -> None:
    """Fixed-size array field makes struct non-RegisterPassable; return uses stub kind."""
    i32 = _i32()
    inner = Struct(
        decl_id="struct:Inner",
        name="Inner",
        c_name="Inner",
        fields=[
            Field(
                name="xs",
                source_name="xs",
                type=Array(element=i32, size=4),
                byte_offset=0,
            )
        ],
        size_bytes=16,
        align_bytes=4,
        is_union=False,
    )
    ref = StructRef(
        decl_id=inner.decl_id,
        name="Inner",
        c_name="Inner",
        is_union=False,
        size_bytes=16,
    )
    fn = Function(
        decl_id="fn:get_inner",
        name="get_inner",
        link_name="get_inner",
        ret=ref,
        params=[],
        is_variadic=False,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[inner, fn],
    )
    au = analyze_unit(unit, MojoEmitOptions())
    tail_fn = au.tail_decls[0]
    assert tail_fn.kind == "non_register_return_stub"


def test_analyze_typedef_skipped_when_name_collides_with_struct() -> None:
    i32 = _i32()
    st = Struct(
        decl_id="struct:S",
        name="S",
        c_name="S",
        fields=[Field(name="x", source_name="x", type=i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    td = Typedef(decl_id="typedef:S", name="S", aliased=i32, canonical=i32)
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st, td])
    au = analyze_unit(unit, MojoEmitOptions())
    assert len(au.tail_decls) == 1
    t = au.tail_decls[0]
    assert t.skip_duplicate is True


def test_analyze_eligible_union_gets_comptime_block() -> None:
    """Members must lower to unique Mojo types for UnsafeUnion."""
    i32 = _i32()
    f32 = _f32()
    u = Struct(
        decl_id="union:U",
        name="U",
        c_name="union U",
        fields=[
            Field(name="a", source_name="a", type=i32, byte_offset=0),
            Field(name="b", source_name="b", type=f32, byte_offset=0),
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=True,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[u])
    au = analyze_unit(unit, MojoEmitOptions())
    assert len(au.unions) == 1
    assert au.unions[0].kind == "unsafe_union"
    assert au.unions[0].mojo_name == "U"
    assert "U" in au.union_alias_names
    assert "U" in au.unsafe_union_names


def test_analyze_typedef_skips_duplicate_name_for_complete_union_alias() -> None:
    i32 = _i32()
    union_decl = Struct(
        decl_id="union:U",
        name="U",
        c_name="union U",
        fields=[
            Field(name="a", source_name="a", type=i32, byte_offset=0),
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
    au = analyze_unit(
        Unit(source_header="t.h", library="t", link_name="t", decls=[union_decl, td]),
        MojoEmitOptions(),
    )
    analyzed_typedef = next(d for d in au.tail_decls if not isinstance(d, AnalyzedFunction))
    assert analyzed_typedef.skip_duplicate is True


def test_analyze_union_with_struct_arm_uses_unsafe_union() -> None:
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
    parts_ref = StructRef(
        decl_id=parts.decl_id,
        name=parts.name,
        c_name=parts.c_name,
        size_bytes=parts.size_bytes,
        is_union=False,
    )
    union_decl = Struct(
        decl_id="union:WithStruct",
        name="WithStruct",
        c_name="union WithStruct",
        fields=[
            Field(name="raw", source_name="raw", type=i32, byte_offset=0),
            Field(name="parts", source_name="parts", type=parts_ref, byte_offset=0),
        ],
        size_bytes=8,
        align_bytes=4,
        is_union=True,
    )
    au = analyze_unit(
        Unit(source_header="t.h", library="t", link_name="t", decls=[parts, union_decl]),
        MojoEmitOptions(),
    )
    analyzed_union = au.unions[0]
    assert analyzed_union.kind == "unsafe_union"
    assert analyzed_union.unsafe_member_types == ("c_int", "Parts")


def test_analyze_precomputes_struct_align_and_passability() -> None:
    i32 = _i32()
    st = Struct(
        decl_id="struct:A",
        name="A",
        c_name="A",
        fields=[Field(name="x", source_name="x", type=i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=8,
        is_union=False,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    au = analyze_unit(unit, MojoEmitOptions(strict_abi=True))
    assert len(au.ordered_structs) == 1
    s = au.ordered_structs[0]
    assert s.register_passable is True
    assert s.align_decorator == 8
    assert s.align_stride_warning is False
    assert s.representation_mode == "fieldwise_exact"


def test_analyze_default_mode_omits_plain_struct_align() -> None:
    i32 = _i32()
    st = Struct(
        decl_id="struct:PortableA",
        name="PortableA",
        c_name="PortableA",
        fields=[Field(name="x", source_name="x", type=i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    au = analyze_unit(unit, MojoEmitOptions())
    s = au.ordered_structs[0]
    assert s.register_passable is True
    assert s.align_decorator is None
    assert s.align_stride_warning is False


def test_analyze_default_mode_keeps_explicit_alignment() -> None:
    i32 = _i32()
    st = Struct(
        decl_id="struct:ExplicitAlign",
        name="ExplicitAlign",
        c_name="ExplicitAlign",
        fields=[Field(name="x", source_name="x", type=i32, byte_offset=0)],
        size_bytes=32,
        align_bytes=16,
        is_union=False,
        requested_align_bytes=16,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    au = analyze_unit(unit, MojoEmitOptions())
    s = au.ordered_structs[0]
    assert s.align_decorator == 16
    assert s.align_stride_warning is False
    assert s.representation_mode == "fieldwise_padded_exact"
    assert len(s.padding_fields) == 1


def test_analyze_typedef_name_in_function_signature_when_typedef_emitted() -> None:
    """TypeRef to a typedef that is emitted uses typedef name in analyzed function signature."""
    i32 = _i32()
    td = Typedef(decl_id="typedef:my_size_t", name="my_size_t", aliased=i32, canonical=i32)
    tr = TypeRef(decl_id=td.decl_id, name="my_size_t", canonical=i32)
    fn = Function(
        decl_id="fn:f",
        name="f",
        link_name="f",
        ret=i32,
        params=[Param(name="n", type=tr)],
        is_variadic=False,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[td, fn])
    au = analyze_unit(unit, MojoEmitOptions())
    assert len(au.tail_decls) == 2
    af = au.tail_decls[1]
    assert af.kind == "wrapper"
    assert af.param_names == ("n",)
    assert "my_size_t" in au.emitted_typedef_mojo_names


def test_analyze_pure_bitfield_struct_separates_storage_from_members() -> None:
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
                name="error",
                source_name="error",
                type=u32,
                byte_offset=0,
                is_bitfield=True,
                bit_offset=1,
                bit_width=1,
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
    au = analyze_unit(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st]), MojoEmitOptions()
    )
    analyzed = au.ordered_structs[0]
    assert analyzed.bitfield_layout is not None
    assert analyzed.fields == ()
    assert analyzed.init_kind == "synthesized"
    assert len(analyzed.synthesized_initializers) == 2
    assert analyzed.synthesized_initializers[0].params == ()
    assert [param.name for param in analyzed.synthesized_initializers[1].params] == [
        "ready",
        "error",
        "enabled",
    ]
    assert [storage.name for storage in analyzed.bitfield_layout.storages] == ["__bf0", "__bf1"]
    assert [member.mojo_name for member in analyzed.bitfield_layout.members] == [
        "ready",
        "error",
        "enabled",
    ]
    assert analyzed.bitfield_layout.members[0].storage_name == "__bf0"
    assert analyzed.bitfield_layout.members[2].storage_name == "__bf1"
    assert analyzed.bitfield_layout.storages[1].type.int_kind == IntKind.UCHAR
    assert analyzed.bitfield_layout.members[2].is_bool is True


def test_analyze_mixed_struct_uses_bitfield_layout_for_bitfield_run() -> None:
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
    au = analyze_unit(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st]), MojoEmitOptions()
    )
    analyzed = au.ordered_structs[0]
    assert [field.mojo_name for field in analyzed.fields] == ["tag"]
    assert analyzed.bitfield_layout is not None
    assert analyzed.init_kind == "fieldwise"
    assert analyzed.synthesized_initializers == ()
    assert [storage.name for storage in analyzed.bitfield_layout.storages] == ["__bf0"]
    assert [member.mojo_name for member in analyzed.bitfield_layout.members] == ["ready"]


def test_analyze_anonymous_only_pure_bitfield_struct_gets_zero_init_only() -> None:
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
    au = analyze_unit(
        Unit(source_header="t.h", library="t", link_name="t", decls=[st]),
        MojoEmitOptions(),
    )
    analyzed = au.ordered_structs[0]
    assert analyzed.init_kind == "synthesized"
    assert len(analyzed.synthesized_initializers) == 1
    assert analyzed.synthesized_initializers[0].params == ()


def test_analyze_function_pointer_returns_use_wrapper_kind() -> None:
    i32 = _i32()
    fp = FunctionPtr(ret=i32, params=[i32, i32], is_variadic=False)
    fp_typedef = Typedef(
        decl_id="typedef:my_binary_op_t",
        name="my_binary_op_t",
        aliased=fp,
        canonical=fp,
    )
    fp_typedef_ref = TypeRef(decl_id=fp_typedef.decl_id, name="my_binary_op_t", canonical=fp)
    fn_direct = Function(
        decl_id="fn:select_direct",
        name="select_direct",
        link_name="select_direct",
        ret=fp,
        params=[],
        is_variadic=False,
    )
    fn_typedef = Function(
        decl_id="fn:select_typedef",
        name="select_typedef",
        link_name="select_typedef",
        ret=fp_typedef_ref,
        params=[],
        is_variadic=False,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[fp_typedef, fn_direct, fn_typedef],
    )
    au = analyze_unit(unit, MojoEmitOptions())
    wrappers = [d for d in au.tail_decls if isinstance(d, AnalyzedFunction)]
    assert len(wrappers) == 2
    assert all(w.kind == "wrapper" for w in wrappers)
    assert "my_binary_op_t" in au.emitted_typedef_mojo_names


def test_analyze_tracks_semantic_imports_and_register_passable_vector_complex() -> None:
    f32 = _f32()
    st = Struct(
        decl_id="struct:VecCx",
        name="VecCx",
        c_name="VecCx",
        fields=[
            Field(
                name="lanes",
                source_name="lanes",
                type=VectorType(element=f32, count=4, size_bytes=16),
                byte_offset=0,
            ),
            Field(
                name="value",
                source_name="value",
                type=ComplexType(element=f32, size_bytes=8),
                byte_offset=16,
            ),
        ],
        size_bytes=24,
        align_bytes=16,
        is_union=False,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    au = analyze_unit(unit, MojoEmitOptions())
    assert au.needs_simd_import is True
    assert au.needs_complex_import is True
    assert au.needs_atomic_import is False
    assert au.semantic_fallback_notes == ()
    assert au.ordered_structs[0].register_passable is True


def test_analyze_atomic_import_and_register_passable_policy() -> None:
    i32 = _i32()
    atomic_i32 = AtomicType(value_type=i32)
    atomic_wchar = AtomicType(
        value_type=IntType(int_kind=IntKind.WCHAR, size_bytes=4, align_bytes=4)
    )
    atomic_box = Struct(
        decl_id="struct:AtomicBox",
        name="AtomicBox",
        c_name="AtomicBox",
        fields=[Field(name="value", source_name="value", type=atomic_i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    wchar_box = Struct(
        decl_id="struct:AtomicFallback",
        name="AtomicFallback",
        c_name="AtomicFallback",
        fields=[Field(name="value", source_name="value", type=atomic_wchar, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            atomic_box,
            wchar_box,
            Function(
                decl_id="fn:get",
                name="get",
                link_name="get",
                ret=atomic_i32,
                params=[],
                is_variadic=False,
            ),
        ],
    )
    au = analyze_unit(unit, MojoEmitOptions())
    assert au.needs_atomic_import is True
    assert any("atomic types were mapped" in note for note in au.semantic_fallback_notes)
    assert au.ordered_structs[0].register_passable is False
    assert au.ordered_structs[0].trait_names == ()
    assert au.ordered_structs[0].emit_fieldwise_init is False
    assert au.ordered_structs[1].register_passable is True
    assert au.ordered_structs[1].trait_names == ("Copyable", "Movable", "RegisterPassable")
    assert au.ordered_structs[1].emit_fieldwise_init is True
