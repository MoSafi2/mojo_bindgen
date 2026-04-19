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
    assert au.unions[0].uses_unsafe_union is True
    assert "U_Union" in au.unsafe_union_names


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
    au = analyze_unit(unit, MojoEmitOptions(emit_align=True))
    assert len(au.ordered_structs) == 1
    s = au.ordered_structs[0]
    assert s.register_passable is True
    assert s.align_decorator == 8
    assert s.align_stride_warning is True


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
    assert au.ordered_structs[1].register_passable is True
