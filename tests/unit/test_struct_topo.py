"""Struct dependency ordering for Mojo emission (no libclang)."""

from __future__ import annotations

from mojo_bindgen.ir import Field, IntKind, IntType, Pointer, Struct, StructRef
from mojo_bindgen.codegen._struct_order import toposort_structs
from mojo_bindgen.codegen.lowering import mojo_ident


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def test_toposort_pointer_to_struct_does_not_force_pointee_first() -> None:
    """struct A { struct B *pb; } — B may be emitted after A (pointer to incomplete)."""
    i32 = _i32()
    b_ref = StructRef(decl_id="struct:B", name="B", c_name="B", is_union=False, size_bytes=4)
    struct_b = Struct(
        decl_id="struct:B",
        name="B",
        c_name="B",
        fields=[Field(name="x", source_name="x", type=i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
    )
    struct_a = Struct(
        decl_id="struct:A",
        name="A",
        c_name="A",
        fields=[
            Field(
                name="pb",
                source_name="pb",
                type=Pointer(pointee=b_ref),
                byte_offset=0,
            )
        ],
        size_bytes=8,
        align_bytes=8,
    )
    ordered = toposort_structs([struct_a, struct_b])
    assert [mojo_ident(s.name.strip() or s.c_name.strip()) for s in ordered] == ["A", "B"]


def test_toposort_value_embed_orders_pointee_before_container() -> None:
    """struct A { struct B b; } — B must be emitted before A."""
    i32 = _i32()
    b_ref = StructRef(decl_id="struct:B", name="B", c_name="B", is_union=False, size_bytes=4)
    struct_b = Struct(
        decl_id="struct:B",
        name="B",
        c_name="B",
        fields=[Field(name="x", source_name="x", type=i32, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
    )
    struct_a = Struct(
        decl_id="struct:A",
        name="A",
        c_name="A",
        fields=[Field(name="b", source_name="b", type=b_ref, byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
    )
    ordered = toposort_structs([struct_a, struct_b])
    assert [mojo_ident(s.name.strip() or s.c_name.strip()) for s in ordered] == ["B", "A"]
