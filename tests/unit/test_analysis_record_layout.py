"""Unit tests for pure CIR record and type layout analysis."""

from __future__ import annotations

from mojo_bindgen.analysis.record_layout import AnalyzeRecordLayoutPass
from mojo_bindgen.analysis.type_layout import type_layout
from mojo_bindgen.ir import Field, IntKind, IntType, Pointer, Struct, StructRef, TargetABI, UnsupportedType


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _abi() -> TargetABI:
    return TargetABI(pointer_size_bytes=8, pointer_align_bytes=8)


def test_type_layout_uses_real_union_alignment_from_cir() -> None:
    union_decl = Struct(
        decl_id="union:Payload",
        name="Payload",
        c_name="Payload",
        fields=[Field(name="value", source_name="value", type=_i32(), byte_offset=0, size_bytes=4)],
        size_bytes=8,
        align_bytes=8,
        is_union=True,
        is_complete=True,
    )
    union_ref = StructRef(
        decl_id=union_decl.decl_id,
        name=union_decl.name,
        c_name=union_decl.c_name,
        is_union=True,
        size_bytes=union_decl.size_bytes,
        align_bytes=union_decl.align_bytes,
    )

    assert type_layout(union_ref) == (8, 8)


def test_type_layout_uses_explicit_pointer_layout_from_cir() -> None:
    assert type_layout(Pointer(pointee=None, size_bytes=4, align_bytes=4)) == (4, 4)


def test_type_layout_returns_none_for_pointer_without_explicit_layout() -> None:
    assert type_layout(Pointer(pointee=None)) is None


def test_type_layout_uses_explicit_structref_layout_without_record_lookup() -> None:
    assert (
        type_layout(
            StructRef(
                decl_id="struct:Payload",
                name="Payload",
                c_name="Payload",
                size_bytes=24,
                align_bytes=8,
            )
        )
        == (24, 8)
    )


def test_record_layout_accepts_union_value_fields_when_layout_is_known() -> None:
    union_decl = Struct(
        decl_id="union:Payload",
        name="Payload",
        c_name="Payload",
        fields=[Field(name="value", source_name="value", type=_i32(), byte_offset=0, size_bytes=4)],
        size_bytes=8,
        align_bytes=8,
        is_union=True,
        is_complete=True,
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
                    decl_id=union_decl.decl_id,
                    name=union_decl.name,
                    c_name=union_decl.c_name,
                    is_union=True,
                    size_bytes=union_decl.size_bytes,
                    align_bytes=union_decl.align_bytes,
                ),
                byte_offset=0,
                size_bytes=union_decl.size_bytes,
            )
        ],
        size_bytes=8,
        align_bytes=8,
        is_complete=True,
    )

    facts = AnalyzeRecordLayoutPass().run(
        holder,
        record_map={holder.decl_id: holder, union_decl.decl_id: union_decl},
        target_abi=_abi(),
    )

    assert len(facts.plain_fields) == 1
    assert facts.plain_fields[0].index == 0
    assert facts.plain_fields[0].byte_offset == 0
    assert facts.plain_fields[0].size_bytes == 8
    assert facts.plain_fields[0].align_bytes == 8
    assert facts.layout_problems == ()


def test_record_layout_reports_unknown_union_member_layout_as_unsupported_metadata() -> None:
    holder = Struct(
        decl_id="struct:Holder",
        name="Holder",
        c_name="Holder",
        fields=[
            Field(
                name="payload",
                source_name="payload",
                type=StructRef(
                    decl_id="union:Missing",
                    name="Missing",
                    c_name="Missing",
                    is_union=True,
                    size_bytes=8,
                ),
                byte_offset=0,
                size_bytes=8,
            )
        ],
        size_bytes=8,
        align_bytes=8,
        is_complete=True,
    )

    facts = AnalyzeRecordLayoutPass().run(
        holder,
        record_map={holder.decl_id: holder},
        target_abi=_abi(),
    )

    assert facts.plain_fields == ()
    assert facts.layout_problems == ("field `payload` has unsupported layout metadata",)


def test_record_layout_keeps_structurally_representable_unsupported_fields() -> None:
    holder = Struct(
        decl_id="struct:Holder",
        name="Holder",
        c_name="Holder",
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
                size_bytes=4,
            )
        ],
        size_bytes=4,
        align_bytes=4,
        is_complete=True,
    )

    facts = AnalyzeRecordLayoutPass().run(
        holder,
        record_map={holder.decl_id: holder},
        target_abi=_abi(),
    )

    assert len(facts.plain_fields) == 1
    assert facts.layout_problems == ()
