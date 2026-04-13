"""Unit tests for :mod:`mojo_bindgen.codegen.mojo_analyze` (no libclang)."""

from __future__ import annotations

from mojo_bindgen.ir import (
    Array,
    Field,
    Function,
    Param,
    Primitive,
    PrimitiveKind,
    Struct,
    StructRef,
    TypeRef,
    Typedef,
    Unit,
)


def _f32() -> Primitive:
    return Primitive(name="float", kind=PrimitiveKind.FLOAT, is_signed=True, size_bytes=4)
from mojo_bindgen.codegen.mojo_analyze import analyze_unit
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions


def _i32() -> Primitive:
    return Primitive(name="int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)


def test_analyze_variadic_function_kind() -> None:
    v = Primitive(name="void", kind=PrimitiveKind.VOID, is_signed=False, size_bytes=0)
    fn = Function(
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
        name="Inner",
        c_name="Inner",
        fields=[
            Field(
                name="xs",
                type=Array(element=i32, size=4),
                byte_offset=0,
            )
        ],
        size_bytes=16,
        align_bytes=4,
        is_union=False,
    )
    ref = StructRef(name="Inner", c_name="Inner", is_union=False, size_bytes=16)
    fn = Function(
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
        name="S",
        c_name="S",
        fields=[Field(name="x", type=i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
        is_union=False,
    )
    td = Typedef(name="S", aliased=i32, canonical=i32)
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st, td])
    au = analyze_unit(unit, MojoEmitOptions())
    assert len(au.tail_decls) == 1
    t = au.tail_decls[0]
    assert t.skip_duplicate is True


def test_analyze_eligible_union_gets_comptime_block() -> None:
    """Members must lower to unique Mojo types for UnsafeUnion comptime."""
    i32 = _i32()
    f32 = _f32()
    u = Struct(
        name="U",
        c_name="union U",
        fields=[
            Field(name="a", type=i32, byte_offset=0),
            Field(name="b", type=f32, byte_offset=0),
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=True,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[u])
    au = analyze_unit(unit, MojoEmitOptions())
    assert len(au.union_blocks) == 1
    ub = au.union_blocks[0]
    assert ub.comptime is not None
    assert "UnsafeUnion" in ub.comptime
    assert "Int32" in ub.comment_block
    assert "Float32" in ub.comment_block


def test_analyze_precomputes_struct_align_and_passability() -> None:
    i32 = _i32()
    st = Struct(
        name="A",
        c_name="A",
        fields=[Field(name="x", type=i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=8,
        is_union=False,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[st])
    au = analyze_unit(unit, MojoEmitOptions(emit_align=True))
    assert len(au.sorted_structs) == 1
    s = au.sorted_structs[0]
    assert s.register_passable is True
    assert s.align_decorator == 8
    assert s.align_stride_warning is True


def test_analyze_typedef_name_in_function_signature_when_typedef_emitted() -> None:
    """TypeRef to a typedef that is emitted uses typedef name in analyzed function signature."""
    i32 = _i32()
    td = Typedef(name="my_size_t", aliased=i32, canonical=i32)
    tr = TypeRef(name="my_size_t", canonical=i32)
    fn = Function(
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
    assert "my_size_t" in af.args_sig
