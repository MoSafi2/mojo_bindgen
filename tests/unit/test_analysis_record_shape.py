from __future__ import annotations

from mojo_bindgen.analysis.record_layout import analyze_record_layout
from mojo_bindgen.analysis.record_shape import (
    RecordStorageKind,
    analyze_record_shape,
    analyze_record_shapes,
)
from mojo_bindgen.ir import (
    Array,
    BuiltinType,
    ByteOrder,
    Field,
    IntKind,
    IntType,
    MojoBuiltin,
    Struct,
    StructRef,
    TargetABI,
)


def _abi() -> TargetABI:
    return TargetABI(
        pointer_size_bytes=8,
        pointer_align_bytes=8,
        byte_order=ByteOrder.LITTLE,
    )


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u8() -> IntType:
    return IntType(int_kind=IntKind.UCHAR, size_bytes=1, align_bytes=1)


def _layout(record: Struct, records: dict[str, Struct] | None = None):
    record_map = records or {record.decl_id: record}
    return analyze_record_layout(record, record_map=record_map, target_abi=_abi())


def test_record_shape_marks_incomplete_records_as_incomplete_storage() -> None:
    opaque = Struct(
        decl_id="struct:Opaque",
        name="Opaque",
        c_name="Opaque",
        fields=[],
        size_bytes=0,
        align_bytes=1,
        is_complete=False,
    )

    facts = analyze_record_shape(opaque, _layout(opaque))

    assert facts.storage_kind == RecordStorageKind.INCOMPLETE
    assert facts.typed_storage_candidate is False


def test_record_shape_marks_layout_problems_as_opaque_storage() -> None:
    broken = Struct(
        decl_id="struct:Broken",
        name="Broken",
        c_name="Broken",
        fields=[Field(name="x", source_name="x", type=_i32(), byte_offset=1, size_bytes=4)],
        size_bytes=8,
        align_bytes=4,
        is_complete=True,
    )

    facts = analyze_record_shape(broken, _layout(broken))

    assert facts.storage_kind == RecordStorageKind.OPAQUE_STORAGE
    assert facts.fallback_reasons


def test_record_shape_extracts_direct_flexible_tail_metadata() -> None:
    packet = Struct(
        decl_id="struct:Packet",
        name="Packet",
        c_name="Packet",
        fields=[
            Field(name="tag", source_name="tag", type=_i32(), byte_offset=0, size_bytes=4),
            Field(
                name="payload",
                source_name="payload",
                type=Array(
                    element=_u8(),
                    size=None,
                    array_kind="flexible",
                    size_bytes=0,
                    align_bytes=1,
                ),
                byte_offset=4,
                size_bytes=0,
                fam_pattern="c99_empty",
            ),
        ],
        size_bytes=4,
        align_bytes=4,
        is_complete=True,
    )

    facts = analyze_record_shape(packet, _layout(packet))

    assert facts.storage_kind == RecordStorageKind.TYPED
    assert facts.flexible_tail is not None
    assert facts.flexible_tail.field_name == "payload"
    assert facts.flexible_tail.element_type == BuiltinType(MojoBuiltin.C_UCHAR)


def test_record_shape_rejects_non_terminal_embedded_flexible_tail() -> None:
    tail = Struct(
        decl_id="struct:Tail",
        name="Tail",
        c_name="Tail",
        fields=[
            Field(
                name="payload",
                source_name="payload",
                type=Array(
                    element=_u8(),
                    size=None,
                    array_kind="flexible",
                    size_bytes=0,
                    align_bytes=1,
                ),
                byte_offset=0,
                size_bytes=0,
                fam_pattern="c99_empty",
            )
        ],
        size_bytes=0,
        align_bytes=1,
        is_complete=True,
    )
    holder = Struct(
        decl_id="struct:Holder",
        name="Holder",
        c_name="Holder",
        fields=[
            Field(
                name="tail",
                source_name="tail",
                type=StructRef(
                    decl_id=tail.decl_id,
                    name=tail.name,
                    c_name=tail.c_name,
                    size_bytes=tail.size_bytes,
                    align_bytes=tail.align_bytes,
                ),
                byte_offset=0,
                size_bytes=0,
            ),
            Field(name="after", source_name="after", type=_i32(), byte_offset=0, size_bytes=4),
        ],
        size_bytes=4,
        align_bytes=4,
        is_complete=True,
    )
    records = {tail.decl_id: tail, holder.decl_id: holder}
    layouts = {decl_id: _layout(record, records) for decl_id, record in records.items()}

    facts = analyze_record_shapes(records, layouts)[holder.decl_id]

    assert facts.storage_kind == RecordStorageKind.OPAQUE_STORAGE
    assert "embedded flexible tail is not terminal" in facts.fallback_reasons[0]
