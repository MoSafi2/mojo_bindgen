"""Unit tests for CIR struct -> MojoIR struct lowering."""

from __future__ import annotations

from mojo_bindgen.analysis.layout import build_register_passable_map
from mojo_bindgen.ir import (
    AtomicType,
    Field,
    IntKind,
    IntType,
    Struct,
    TargetABI,
    Unit,
    UnsupportedType,
)
from mojo_bindgen.mojo_ir import (
    ArrayType,
    BitfieldField,
    BitfieldGroupMember,
    BuiltinType,
    DTypeArg,
    Initializer,
    InitializerParam,
    MojoBuiltin,
    PaddingMember,
    ParametricBase,
    ParametricType,
    StoredMember,
    StructKind,
    StructTraits,
)
from mojo_bindgen.new_analysis.struct_lowering import StructLoweringContext, lower_struct
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u32() -> IntType:
    return IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)


def _bool() -> IntType:
    return IntType(int_kind=IntKind.BOOL, size_bytes=1, align_bytes=1)


def _abi() -> TargetABI:
    return TargetABI(pointer_size_bytes=8, pointer_align_bytes=8)


def _context_for(*decls: Struct) -> StructLoweringContext:
    struct_map = {decl.decl_id: decl for decl in decls}
    return StructLoweringContext(
        struct_map=struct_map,
        register_passable_by_decl_id=build_register_passable_map(struct_map),
        target_abi=_abi(),
        type_lowerer=LowerTypePass(),
    )


def test_lower_struct_keeps_incomplete_records_opaque_with_explicit_align_none() -> None:
    decl = Struct(
        decl_id="struct:Opaque",
        name="Opaque",
        c_name="Opaque",
        fields=[],
        size_bytes=0,
        align_bytes=1,
        is_complete=False,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.name == "Opaque"
    assert lowered.kind == StructKind.OPAQUE
    assert lowered.align is None
    assert lowered.align_decorator is None
    assert lowered.fieldwise_init is False
    assert lowered.traits == [StructTraits.COPYABLE, StructTraits.MOVABLE]
    assert lowered.members == []
    assert lowered.initializers == []
    assert lowered.diagnostics == []


def test_lower_struct_lowers_fieldwise_exact_structs_with_traits() -> None:
    decl = Struct(
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

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.kind == StructKind.PLAIN
    assert lowered.align == 4
    assert lowered.align_decorator is None
    assert lowered.fieldwise_init is True
    assert lowered.traits == [
        StructTraits.COPYABLE,
        StructTraits.MOVABLE,
        StructTraits.REGISTER_PASSABLE,
    ]
    assert lowered.members == [
        StoredMember(name="count", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=0),
        StoredMember(name="flags", type=BuiltinType(MojoBuiltin.C_UINT), byte_offset=4),
    ]


def test_lower_struct_synthesizes_padding_members_for_exact_layout_gaps() -> None:
    decl = Struct(
        decl_id="struct:Padded",
        name="Padded",
        c_name="Padded",
        fields=[
            Field(
                name="tag",
                source_name="tag",
                type=IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1),
                byte_offset=0,
            ),
            Field(name="value", source_name="value", type=_i32(), byte_offset=8),
        ],
        size_bytes=12,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.fieldwise_init is True
    assert lowered.members == [
        StoredMember(name="tag", type=BuiltinType(MojoBuiltin.C_UCHAR), byte_offset=0),
        PaddingMember(name="__pad0", size_bytes=4, byte_offset=4),
        StoredMember(name="value", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=8),
    ]


def test_lower_struct_falls_back_to_opaque_storage_for_unrepresentable_layout() -> None:
    decl = Struct(
        decl_id="struct:Packed",
        name="Packed",
        c_name="Packed",
        fields=[
            Field(
                name="tag",
                source_name="tag",
                type=IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1),
                byte_offset=0,
            ),
            Field(name="value", source_name="value", type=_i32(), byte_offset=1),
        ],
        size_bytes=5,
        align_bytes=1,
        is_complete=True,
        is_packed=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.fieldwise_init is False
    assert len(lowered.members) == 1
    assert lowered.members[0].name == "storage"
    assert lowered.members[0].size_bytes == 5
    assert lowered.diagnostics
    assert all(note.category == "struct_lowering" for note in lowered.diagnostics)
    assert "opaque storage emitted" in lowered.diagnostics[0].message


def test_lower_struct_keeps_atomic_field_types_and_drops_traits() -> None:
    decl = Struct(
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

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.traits == []
    assert lowered.fieldwise_init is False
    assert lowered.members[0] == StoredMember(
        name="counter",
        type=ParametricType(base=ParametricBase.ATOMIC, args=[DTypeArg("DType.int32")]),
        byte_offset=0,
    )


def test_lower_struct_lowers_pure_bitfield_structs_with_synthesized_initializers() -> None:
    decl = Struct(
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
                name="state",
                source_name="state",
                type=_u32(),
                byte_offset=0,
                is_bitfield=True,
                bit_offset=1,
                bit_width=3,
            ),
            Field(
                name="",
                source_name="",
                type=_u32(),
                byte_offset=4,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=32,
                bit_width=0,
            ),
            Field(
                name="enabled",
                source_name="enabled",
                type=_bool(),
                byte_offset=4,
                is_bitfield=True,
                bit_offset=32,
                bit_width=1,
            ),
        ],
        size_bytes=8,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.fieldwise_init is False
    assert lowered.members == [
        BitfieldGroupMember(
            storage_name="__bf0",
            storage_type=BuiltinType(MojoBuiltin.C_UINT),
            byte_offset=0,
            fields=[
                BitfieldField(
                    name="ready",
                    logical_type=BuiltinType(MojoBuiltin.C_UINT),
                    bit_offset=0,
                    bit_width=1,
                    signed=False,
                ),
                BitfieldField(
                    name="state",
                    logical_type=BuiltinType(MojoBuiltin.C_UINT),
                    bit_offset=1,
                    bit_width=3,
                    signed=False,
                ),
            ],
        ),
        BitfieldGroupMember(
            storage_name="__bf1",
            storage_type=BuiltinType(MojoBuiltin.C_UCHAR),
            byte_offset=4,
            fields=[
                BitfieldField(
                    name="enabled",
                    logical_type=BuiltinType(MojoBuiltin.BOOL),
                    bit_offset=32,
                    bit_width=1,
                    signed=False,
                    bool_semantics=True,
                )
            ],
        ),
    ]
    assert lowered.initializers == [
        Initializer(params=[]),
        Initializer(
            params=[
                InitializerParam(name="ready", type=BuiltinType(MojoBuiltin.C_UINT)),
                InitializerParam(name="state", type=BuiltinType(MojoBuiltin.C_UINT)),
                InitializerParam(name="enabled", type=BuiltinType(MojoBuiltin.BOOL)),
            ]
        ),
    ]


def test_lower_struct_lowers_mixed_bitfield_structs_in_byte_offset_order() -> None:
    decl = Struct(
        decl_id="struct:MixedBits",
        name="MixedBits",
        c_name="MixedBits",
        fields=[
            Field(name="tag", source_name="tag", type=_u32(), byte_offset=0),
            Field(
                name="signed_bits",
                source_name="signed_bits",
                type=_i32(),
                byte_offset=4,
                is_bitfield=True,
                bit_offset=32,
                bit_width=5,
            ),
            Field(
                name="enabled",
                source_name="enabled",
                type=_bool(),
                byte_offset=4,
                is_bitfield=True,
                bit_offset=37,
                bit_width=1,
            ),
        ],
        size_bytes=8,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.fieldwise_init is True
    assert lowered.initializers == []
    assert lowered.members[0] == StoredMember(
        name="tag",
        type=BuiltinType(MojoBuiltin.C_UINT),
        byte_offset=0,
    )
    assert isinstance(lowered.members[1], BitfieldGroupMember)
    group = lowered.members[1]
    assert group.storage_name == "__bf0"
    assert group.byte_offset == 4
    assert [field.name for field in group.fields] == ["signed_bits", "enabled"]
    assert group.fields[0].signed is True
    assert group.fields[1].bool_semantics is True


def test_lower_struct_splits_bitfield_groups_on_zero_width_barriers() -> None:
    decl = Struct(
        decl_id="struct:SplitBits",
        name="SplitBits",
        c_name="SplitBits",
        fields=[
            Field(
                name="left",
                source_name="left",
                type=_u32(),
                byte_offset=0,
                is_bitfield=True,
                bit_offset=0,
                bit_width=1,
            ),
            Field(
                name="",
                source_name="",
                type=_u32(),
                byte_offset=0,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=31,
                bit_width=0,
            ),
            Field(
                name="right",
                source_name="right",
                type=_u32(),
                byte_offset=4,
                is_bitfield=True,
                bit_offset=32,
                bit_width=1,
            ),
        ],
        size_bytes=8,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert [member.storage_name for member in lowered.members] == ["__bf0", "__bf1"]
    assert [member.byte_offset for member in lowered.members] == [0, 4]


def test_lower_struct_emits_zero_init_only_for_anonymous_only_bitfield_struct() -> None:
    decl = Struct(
        decl_id="struct:AnonBits",
        name="AnonBits",
        c_name="AnonBits",
        fields=[
            Field(
                name="",
                source_name="",
                type=_u32(),
                byte_offset=0,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=0,
                bit_width=8,
            ),
        ],
        size_bytes=4,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.fieldwise_init is False
    assert len(lowered.initializers) == 1
    assert lowered.initializers[0] == Initializer(params=[])


def test_context_building_matches_unit_register_passable_expectations() -> None:
    decl = Struct(
        decl_id="struct:Widget",
        name="Widget",
        c_name="Widget",
        fields=[Field(name="count", source_name="count", type=_i32(), byte_offset=0)],
        size_bytes=4,
        align_bytes=4,
        is_complete=True,
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", target_abi=_abi(), decls=[decl])

    context = _context_for(*[d for d in unit.decls if isinstance(d, Struct)])

    assert context.register_passable_by_decl_id[decl.decl_id] is True


def test_lower_struct_falls_back_only_after_mojo_type_lowering_failure() -> None:
    decl = Struct(
        decl_id="struct:LoweringFallback",
        name="LoweringFallback",
        c_name="LoweringFallback",
        fields=[
            Field(
                name="mystery",
                source_name="mystery",
                type=UnsupportedType(
                    category="unsupported_extension",
                    spelling="mystery_t",
                    reason="not modeled",
                    size_bytes=4,
                    align_bytes=4,
                ),
                byte_offset=0,
            )
        ],
        size_bytes=4,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.fieldwise_init is True
    assert lowered.diagnostics == []
    assert lowered.members == [
        StoredMember(
            name="mystery",
            type=ArrayType(element=BuiltinType(MojoBuiltin.UINT8), count=4),
            byte_offset=0,
        )
    ]
