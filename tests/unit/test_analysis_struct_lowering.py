"""Unit tests for CIR struct -> MojoIR struct lowering."""

from __future__ import annotations

from mojo_bindgen.analysis.struct_lowering import StructLoweringContext, lower_struct
from mojo_bindgen.analysis.type_lowering import LowerTypePass
from mojo_bindgen.ir import (
    ByteOrder,
    AtomicType,
    Field,
    IntKind,
    IntType,
    Struct,
    StructRef,
    TargetABI,
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
    NamedType,
    PaddingMember,
    ParametricBase,
    ParametricType,
    StoredMember,
    StructKind,
)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u32() -> IntType:
    return IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)


def _bool() -> IntType:
    return IntType(int_kind=IntKind.BOOL, size_bytes=1, align_bytes=1)


def _abi() -> TargetABI:
    return TargetABI(
        pointer_size_bytes=8,
        pointer_align_bytes=8,
        byte_order=ByteOrder.LITTLE,
    )


def _field(
    *,
    name: str,
    source_name: str,
    type,
    byte_offset: int,
    size_bytes: int | None = None,
    **kwargs,
) -> Field:
    if size_bytes is None:
        size_bytes = getattr(type, "size_bytes", 0) or 0
    return Field(
        name=name,
        source_name=source_name,
        type=type,
        byte_offset=byte_offset,
        size_bytes=size_bytes,
        **kwargs,
    )


def _context_for(*decls: Struct) -> StructLoweringContext:
    record_map = {decl.decl_id: decl for decl in decls}
    return StructLoweringContext(
        record_map=record_map,
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
    assert lowered.traits == []
    assert lowered.members == []
    assert lowered.initializers == []
    assert lowered.diagnostics == []


def test_lower_struct_lowers_fieldwise_exact_structs_without_policies() -> None:
    decl = Struct(
        decl_id="struct:Widget",
        name="Widget",
        c_name="Widget",
        fields=[
            _field(name="count", source_name="count", type=_i32(), byte_offset=0),
            _field(name="flags", source_name="flags", type=_u32(), byte_offset=4),
        ],
        size_bytes=8,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.kind == StructKind.PLAIN
    assert lowered.align == 4
    assert lowered.align_decorator is None
    assert lowered.fieldwise_init is False
    assert lowered.traits == []
    assert lowered.members == [
        StoredMember(index=0, name="count", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=0),
        StoredMember(index=1, name="flags", type=BuiltinType(MojoBuiltin.C_UINT), byte_offset=4),
    ]


def test_lower_struct_synthesizes_padding_members_for_exact_layout_gaps() -> None:
    decl = Struct(
        decl_id="struct:Padded",
        name="Padded",
        c_name="Padded",
        fields=[
            _field(
                name="tag",
                source_name="tag",
                type=IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1),
                byte_offset=0,
            ),
            _field(name="value", source_name="value", type=_i32(), byte_offset=8),
        ],
        size_bytes=12,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.fieldwise_init is False
    assert lowered.members == [
        StoredMember(index=0, name="tag", type=BuiltinType(MojoBuiltin.C_UCHAR), byte_offset=0),
        PaddingMember(name="__pad0", size_bytes=4, byte_offset=4),
        StoredMember(index=1, name="value", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=8),
    ]


def test_lower_struct_keeps_union_members_typed_and_preserves_padding() -> None:
    union_decl = Struct(
        decl_id="union:Payload",
        name="Payload",
        c_name="Payload",
        fields=[_field(name="value", source_name="value", type=_i32(), byte_offset=0)],
        size_bytes=8,
        align_bytes=8,
        is_union=True,
        is_complete=True,
    )
    decl = Struct(
        decl_id="struct:Holder",
        name="Holder",
        c_name="Holder",
        fields=[
            _field(
                name="tag",
                source_name="tag",
                type=IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1),
                byte_offset=0,
            ),
            _field(
                name="payload",
                source_name="payload",
                type=StructRef(
                    decl_id=union_decl.decl_id,
                    name=union_decl.name,
                    c_name=union_decl.c_name,
                    is_union=True,
                    size_bytes=union_decl.size_bytes,
                    align_bytes=union_decl.align_bytes,
                ),
                byte_offset=8,
            ),
            _field(name="tail", source_name="tail", type=_u32(), byte_offset=16),
        ],
        size_bytes=24,
        align_bytes=8,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl, union_decl))

    assert lowered.fieldwise_init is False
    assert lowered.members == [
        StoredMember(index=0, name="tag", type=BuiltinType(MojoBuiltin.C_UCHAR), byte_offset=0),
        StoredMember(index=1, name="payload", type=NamedType("Payload"), byte_offset=8),
        StoredMember(index=2, name="tail", type=BuiltinType(MojoBuiltin.C_UINT), byte_offset=16),
    ]


def test_lower_struct_omits_trailing_padding_explained_by_struct_alignment() -> None:
    decl = Struct(
        decl_id="struct:Aligned",
        name="Aligned",
        c_name="Aligned",
        fields=[_field(name="value", source_name="value", type=_i32(), byte_offset=0)],
        size_bytes=16,
        align_bytes=16,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.members == [
        StoredMember(index=0, name="value", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=0),
    ]


def test_lower_struct_falls_back_to_opaque_storage_for_unrepresentable_layout() -> None:
    decl = Struct(
        decl_id="struct:Packed",
        name="Packed",
        c_name="Packed",
        fields=[
            _field(
                name="tag",
                source_name="tag",
                type=IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1),
                byte_offset=0,
            ),
            _field(name="value", source_name="value", type=_i32(), byte_offset=1),
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
            _field(
                name="counter",
                source_name="counter",
                type=AtomicType(value_type=_i32()),
                byte_offset=0,
                size_bytes=4,
            ),
            _field(name="flags", source_name="flags", type=_u32(), byte_offset=4),
        ],
        size_bytes=8,
        align_bytes=4,
        is_complete=True,
    )

    lowered = lower_struct(decl, context=_context_for(decl))

    assert lowered.traits == []
    assert lowered.fieldwise_init is False
    assert lowered.members[0] == StoredMember(
        index=0,
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
            _field(
                name="ready",
                source_name="ready",
                type=_u32(),
                byte_offset=0,
                is_bitfield=True,
                bit_offset=0,
                bit_width=1,
            ),
            _field(
                name="state",
                source_name="state",
                type=_u32(),
                byte_offset=0,
                is_bitfield=True,
                bit_offset=1,
                bit_width=3,
            ),
            _field(
                name="",
                source_name="",
                type=_u32(),
                byte_offset=4,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=32,
                bit_width=0,
            ),
            _field(
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
            first_index=0,
            storage_width_bits=32,
            fields=[
                BitfieldField(
                    index=0,
                    name="ready",
                    logical_type=BuiltinType(MojoBuiltin.C_UINT),
                    bit_offset=0,
                    bit_width=1,
                    signed=False,
                ),
                BitfieldField(
                    index=1,
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
            first_index=3,
            storage_width_bits=8,
            fields=[
                BitfieldField(
                    index=3,
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
            _field(name="tag", source_name="tag", type=_u32(), byte_offset=0),
            _field(
                name="signed_bits",
                source_name="signed_bits",
                type=_i32(),
                byte_offset=4,
                is_bitfield=True,
                bit_offset=32,
                bit_width=5,
            ),
            _field(
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

    assert lowered.fieldwise_init is False
    assert lowered.initializers == []
    assert lowered.members[0] == StoredMember(
        index=0,
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
            _field(
                name="left",
                source_name="left",
                type=_u32(),
                byte_offset=0,
                is_bitfield=True,
                bit_offset=0,
                bit_width=1,
            ),
            _field(
                name="",
                source_name="",
                type=_u32(),
                byte_offset=0,
                is_anonymous=True,
                is_bitfield=True,
                bit_offset=31,
                bit_width=0,
            ),
            _field(
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
            _field(
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


def test_lower_struct_omits_register_passable_when_field_references_incomplete_struct() -> None:
    child = Struct(
        decl_id="struct:Child",
        name="Child",
        c_name="Child",
        fields=[],
        size_bytes=0,
        align_bytes=1,
        is_complete=False,
    )
    holder = Struct(
        decl_id="struct:Holder",
        name="Holder",
        c_name="Holder",
        fields=[
            _field(
                name="child",
                source_name="child",
                type=StructRef(
                    decl_id=child.decl_id,
                    name=child.name,
                    c_name=child.c_name,
                    is_union=False,
                    size_bytes=child.size_bytes,
                    align_bytes=child.align_bytes,
                ),
                byte_offset=0,
            )
        ],
        size_bytes=8,
        align_bytes=8,
        is_complete=True,
    )

    lowered = lower_struct(holder, context=_context_for(holder, child))

    assert lowered.fieldwise_init is False
    assert lowered.traits == []


def test_lower_struct_omits_register_passable_for_recursive_struct_cycle() -> None:
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
        _field(
            name="right",
            source_name="right",
            type=StructRef(
                decl_id=right.decl_id,
                name=right.name,
                c_name=right.c_name,
                is_union=False,
                size_bytes=right.size_bytes,
                align_bytes=right.align_bytes,
            ),
            byte_offset=0,
        )
    ]
    right.fields = [
        _field(
            name="left",
            source_name="left",
            type=StructRef(
                decl_id=left.decl_id,
                name=left.name,
                c_name=left.c_name,
                is_union=False,
                size_bytes=left.size_bytes,
                align_bytes=left.align_bytes,
            ),
            byte_offset=0,
        )
    ]

    lowered = lower_struct(left, context=_context_for(left, right))

    assert lowered.fieldwise_init is False
    assert lowered.traits == []


def test_lower_struct_falls_back_only_after_mojo_type_lowering_failure() -> None:
    decl = Struct(
        decl_id="struct:LoweringFallback",
        name="LoweringFallback",
        c_name="LoweringFallback",
        fields=[
            _field(
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

    assert lowered.fieldwise_init is False
    assert lowered.diagnostics == []
    assert lowered.members == [
        StoredMember(
            index=0,
            name="mystery",
            type=ArrayType(element=BuiltinType(MojoBuiltin.UINT8), count=4),
            byte_offset=0,
        )
    ]
