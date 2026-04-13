"""Struct dependency ordering for Mojo emission (no libclang)."""

from __future__ import annotations

from mojo_bindgen.ir import Pointer, Primitive, PrimitiveKind, Struct, StructRef, Field
from mojo_bindgen.codegen._struct_order import toposort_structs
from mojo_bindgen.codegen.lowering import mojo_ident


def _i32() -> Primitive:
    return Primitive(name="int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)


def test_toposort_pointer_to_struct_does_not_force_pointee_first() -> None:
    """struct A { struct B *pb; } — B may be emitted after A (pointer to incomplete)."""
    i32 = _i32()
    b_ref = StructRef(name="B", c_name="B", is_union=False, size_bytes=4)
    struct_b = Struct(
        name="B",
        c_name="B",
        fields=[Field("x", i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
    )
    struct_a = Struct(
        name="A",
        c_name="A",
        fields=[Field("pb", Pointer(pointee=b_ref, is_const=False), byte_offset=0)],
        size_bytes=8,
        align_bytes=8,
    )
    ordered = toposort_structs([struct_a, struct_b])
    assert [mojo_ident(s.name.strip() or s.c_name.strip()) for s in ordered] == ["A", "B"]


def test_toposort_value_embed_orders_pointee_before_container() -> None:
    """struct A { struct B b; } — B must be emitted before A."""
    i32 = _i32()
    b_ref = StructRef(name="B", c_name="B", is_union=False, size_bytes=4)
    struct_b = Struct(
        name="B",
        c_name="B",
        fields=[Field("x", i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
    )
    struct_a = Struct(
        name="A",
        c_name="A",
        fields=[Field("b", b_ref, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
    )
    ordered = toposort_structs([struct_a, struct_b])
    assert [mojo_ident(s.name.strip() or s.c_name.strip()) for s in ordered] == ["B", "A"]
