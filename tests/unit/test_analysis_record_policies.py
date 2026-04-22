from __future__ import annotations

from mojo_bindgen.analysis import assign_record_policies, lower_unit
from mojo_bindgen.ir import (
    AtomicType,
    Field,
    IntKind,
    IntType,
    Struct,
    StructRef,
    TargetABI,
    Unit,
)
from mojo_bindgen.mojo_ir import StructDecl, StructTraits


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u32() -> IntType:
    return IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)


def _u8() -> IntType:
    return IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1)


def _bool() -> IntType:
    return IntType(int_kind=IntKind.BOOL, size_bytes=1, align_bytes=1)


def _abi() -> TargetABI:
    return TargetABI(pointer_size_bytes=8, pointer_align_bytes=8)


def _lowered_structs(*decls: Struct) -> list[StructDecl]:
    lowered = lower_unit(
        Unit(
            source_header="demo.h",
            library="demo",
            link_name="demo",
            target_abi=_abi(),
            decls=list(decls),
        )
    )
    module = assign_record_policies(lowered)
    return [decl for decl in module.decls if isinstance(decl, StructDecl)]


def test_assign_record_policies_marks_fieldwise_exact_struct_register_passable() -> None:
    [widget] = _lowered_structs(
        Struct(
            decl_id="struct:Widget",
            name="Widget",
            c_name="Widget",
            fields=[
                Field(name="count", source_name="count", type=_i32(), byte_offset=0),
                Field(name="flags", source_name="flags", type=_u32(), byte_offset=4),
            ],
            size_bytes=8,
            align_bytes=4,
            is_complete=True,
        )
    )

    assert widget.fieldwise_init is True
    assert widget.traits == [
        StructTraits.COPYABLE,
        StructTraits.MOVABLE,
        StructTraits.REGISTER_PASSABLE,
    ]


def test_assign_record_policies_keeps_padding_struct_non_register_passable() -> None:
    [padded] = _lowered_structs(
        Struct(
            decl_id="struct:Padded",
            name="Padded",
            c_name="Padded",
            fields=[
                Field(name="tag", source_name="tag", type=_u8(), byte_offset=0),
                Field(name="value", source_name="value", type=_i32(), byte_offset=8),
            ],
            size_bytes=12,
            align_bytes=4,
            is_complete=True,
        )
    )

    assert padded.fieldwise_init is True
    assert padded.traits == [StructTraits.COPYABLE, StructTraits.MOVABLE]


def test_assign_record_policies_keeps_incomplete_struct_copyable_only() -> None:
    [opaque] = _lowered_structs(
        Struct(
            decl_id="struct:Opaque",
            name="Opaque",
            c_name="Opaque",
            fields=[],
            size_bytes=0,
            align_bytes=1,
            is_complete=False,
        )
    )

    assert opaque.fieldwise_init is False
    assert opaque.traits == [StructTraits.COPYABLE, StructTraits.MOVABLE]


def test_assign_record_policies_drops_traits_for_representable_atomic_storage() -> None:
    [atomic_holder] = _lowered_structs(
        Struct(
            decl_id="struct:AtomicHolder",
            name="AtomicHolder",
            c_name="AtomicHolder",
            fields=[
                Field(
                    name="counter",
                    source_name="counter",
                    type=AtomicType(value_type=_i32()),
                    byte_offset=0,
                ),
                Field(name="flags", source_name="flags", type=_u32(), byte_offset=4),
            ],
            size_bytes=8,
            align_bytes=4,
            is_complete=True,
        )
    )

    assert atomic_holder.fieldwise_init is False
    assert atomic_holder.traits == []


def test_assign_record_policies_keeps_pure_bitfield_struct_non_fieldwise_init() -> None:
    [bits] = _lowered_structs(
        Struct(
            decl_id="struct:Bits",
            name="Bits",
            c_name="Bits",
            fields=[
                Field(
                    name="ready",
                    source_name="ready",
                    type=_u32(),
                    byte_offset=0,
                    is_bitfield=True,
                    bit_offset=0,
                    bit_width=1,
                ),
                Field(
                    name="enabled",
                    source_name="enabled",
                    type=_bool(),
                    byte_offset=0,
                    is_bitfield=True,
                    bit_offset=1,
                    bit_width=1,
                ),
            ],
            size_bytes=4,
            align_bytes=4,
            is_complete=True,
        )
    )

    assert bits.fieldwise_init is False
    assert bits.traits == [StructTraits.COPYABLE, StructTraits.MOVABLE]


def test_assign_record_policies_breaks_recursive_register_passable_cycles() -> None:
    left = Struct(
        decl_id="struct:Left",
        name="Left",
        c_name="Left",
        fields=[],
        size_bytes=8,
        align_bytes=8,
        is_complete=True,
    )
    right = Struct(
        decl_id="struct:Right",
        name="Right",
        c_name="Right",
        fields=[],
        size_bytes=8,
        align_bytes=8,
        is_complete=True,
    )
    left.fields = [
        Field(
            name="right",
            source_name="right",
            type=StructRef(
                decl_id=right.decl_id,
                name=right.name,
                c_name=right.c_name,
                is_union=False,
                size_bytes=right.size_bytes,
            ),
            byte_offset=0,
        )
    ]
    right.fields = [
        Field(
            name="left",
            source_name="left",
            type=StructRef(
                decl_id=left.decl_id,
                name=left.name,
                c_name=left.c_name,
                is_union=False,
                size_bytes=left.size_bytes,
            ),
            byte_offset=0,
        )
    ]

    left_decl, right_decl = _lowered_structs(left, right)

    assert left_decl.fieldwise_init is True
    assert right_decl.fieldwise_init is True
    assert left_decl.traits == [StructTraits.COPYABLE, StructTraits.MOVABLE]
    assert right_decl.traits == [StructTraits.COPYABLE, StructTraits.MOVABLE]
