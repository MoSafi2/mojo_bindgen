"""Lower CIR structs into MojoIR structs using pure layout facts plus Mojo planning."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.common import _mojo_align_decorator_ok
from mojo_bindgen.analysis.lowering_support import (
    field_display_name,
    field_mojo_name,
    record_name,
    struct_note,
    try_lower_type,
)
from mojo_bindgen.analysis.record_layout import RecordLayoutFacts, analyze_record_layout
from mojo_bindgen.analysis.type_lowering import LowerTypePass
from mojo_bindgen.ir import AtomicType, Struct, TargetABI
from mojo_bindgen.mojo_ir import (
    BitfieldField,
    BitfieldGroupMember,
    Initializer,
    InitializerParam,
    OpaqueStorageMember,
    PaddingMember,
    ParametricBase,
    ParametricType,
    StoredMember,
    StructDecl,
    StructKind,
)


class StructLoweringError(ValueError):
    """Raised when a CIR struct declaration cannot be lowered to MojoIR."""


@dataclass
class StructLoweringContext:
    record_map: dict[str, Struct]
    target_abi: TargetABI
    type_lowerer: LowerTypePass


def lower_struct(decl: Struct, *, context: StructLoweringContext) -> StructDecl:
    """Lower one top-level CIR struct declaration to MojoIR."""

    if decl.is_union:
        raise StructLoweringError(
            f"expected non-union Struct declaration, got union {decl.decl_id!r}"
        )

    facts = analyze_record_layout(
        decl,
        record_map=context.record_map,
        target_abi=context.target_abi,
    )
    if not facts.is_complete:
        return _incomplete_struct_decl(decl)
    if facts.layout_problems:
        return _opaque_storage_struct_decl(decl, facts)

    plain_fields, lowered_bitfield_groups, diagnostic_notes, fallback_reasons = (
        _lower_typed_members(
            decl,
            facts,
            context=context,
        )
    )
    if fallback_reasons:
        return _opaque_storage_struct_decl(
            decl,
            facts,
            diagnostic_notes=diagnostic_notes,
            fallback_reasons=fallback_reasons,
        )

    align, align_decorator = _compute_align_policy(facts, uses_opaque_storage=False)
    return StructDecl(
        name=record_name(decl),
        kind=StructKind.PLAIN,
        traits=[],
        align=align,
        align_decorator=align_decorator,
        fieldwise_init=False,
        members=_build_members(decl, facts, plain_fields, lowered_bitfield_groups),
        initializers=_build_initializers(
            facts,
            lowered_bitfield_groups,
            uses_opaque_storage=False,
        ),
        diagnostics=_build_diagnostics(
            facts.layout_problems,
            diagnostic_notes=diagnostic_notes,
            fallback_reasons=(),
        ),
    )


def _lower_typed_members(
    decl: Struct,
    facts: RecordLayoutFacts,
    *,
    context: StructLoweringContext,
) -> tuple[list[StoredMember], list[BitfieldGroupMember], tuple[str, ...], tuple[str, ...]]:
    plain_fields: list[StoredMember] = []
    lowered_bitfield_groups: list[BitfieldGroupMember] = []
    diagnostic_notes: list[str] = []
    fallback_reasons: list[str] = []

    for field_fact in facts.plain_fields:
        field = decl.fields[field_fact.index]
        display_name = field_display_name(field, field_fact.index)
        lowered_type, reason = try_lower_type(
            context.type_lowerer,
            field.type,
            subject=f"field `{display_name}`",
            failure_suffix="opaque storage emitted",
        )
        if reason is not None or lowered_type is None:
            if reason is not None:
                fallback_reasons.append(reason)
            continue
        if isinstance(field.type, AtomicType) and not (
            isinstance(lowered_type, ParametricType) and lowered_type.base == ParametricBase.ATOMIC
        ):
            note = (
                "some atomic types were mapped to their underlying non-atomic Mojo type "
                "because Atomic[dtype] was not representable"
            )
            if note not in diagnostic_notes:
                diagnostic_notes.append(note)
        plain_fields.append(
            StoredMember(
                index=field_fact.index,
                name=field_mojo_name(field, field_fact.index),
                type=lowered_type,
                byte_offset=field_fact.byte_offset,
            )
        )

    for run_layout in facts.bitfield_runs:
        lowered_storage_type, reason = try_lower_type(
            context.type_lowerer,
            run_layout.unsigned_storage_type,
            subject=f"bitfield storage `{run_layout.name}`",
            failure_suffix="opaque storage emitted",
        )
        if reason is not None or lowered_storage_type is None:
            if reason is not None:
                fallback_reasons.append(reason)
            continue

        lowered_fields: list[BitfieldField] = []
        for field_layout in run_layout.fields:
            display_name = field_display_name(field_layout.field, field_layout.index)
            logical_type, reason = try_lower_type(
                context.type_lowerer,
                field_layout.logical_type,
                subject=f"bitfield `{display_name}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None or logical_type is None:
                if reason is not None:
                    fallback_reasons.append(reason)
                continue
            lowered_fields.append(
                BitfieldField(
                    index=field_layout.index,
                    name=field_mojo_name(field_layout.field, field_layout.index),
                    logical_type=logical_type,
                    bit_offset=field_layout.bit_offset,
                    bit_width=field_layout.bit_width,
                    signed=field_layout.signed,
                    bool_semantics=field_layout.bool_semantics,
                )
            )

        lowered_bitfield_groups.append(
            BitfieldGroupMember(
                storage_name=run_layout.name,
                storage_type=lowered_storage_type,
                byte_offset=run_layout.byte_offset,
                first_index=run_layout.first_index,
                storage_width_bits=run_layout.storage_width_bits,
                fields=lowered_fields,
            )
        )

    return (
        plain_fields,
        lowered_bitfield_groups,
        tuple(diagnostic_notes),
        tuple(fallback_reasons),
    )


def _build_members(
    decl: Struct,
    facts: RecordLayoutFacts,
    plain_fields: list[StoredMember],
    lowered_bitfield_groups: list[BitfieldGroupMember],
) -> list[StoredMember | PaddingMember | OpaqueStorageMember | BitfieldGroupMember]:
    members_with_offsets: list[
        tuple[int, int, StoredMember | PaddingMember | OpaqueStorageMember | BitfieldGroupMember]
    ] = [(field.byte_offset, field.index, field) for field in plain_fields]

    if not facts.is_pure_bitfield:
        pad_order_base = len(decl.fields) + len(lowered_bitfield_groups)
        for i, padding in enumerate(facts.padding_spans):
            members_with_offsets.append(
                (
                    padding.byte_offset,
                    pad_order_base + i,
                    PaddingMember(
                        name=padding.name,
                        size_bytes=padding.size_bytes,
                        byte_offset=padding.byte_offset,
                    ),
                )
            )

    for group in lowered_bitfield_groups:
        members_with_offsets.append((group.byte_offset, group.first_index, group))

    members_with_offsets.sort(key=lambda item: (item[0], item[1]))
    return [member for _, _, member in members_with_offsets]


def _build_diagnostics(
    layout_problems: tuple[str, ...],
    *,
    diagnostic_notes: tuple[str, ...],
    fallback_reasons: tuple[str, ...],
) -> list:
    return [
        *(struct_note(f"{problem}; opaque storage emitted") for problem in layout_problems),
        *(struct_note(note) for note in diagnostic_notes),
        *(struct_note(reason) for reason in fallback_reasons),
    ]


def _compute_align_policy(
    facts: RecordLayoutFacts,
    *,
    uses_opaque_storage: bool,
) -> tuple[int | None, int | None]:
    align = facts.align_bytes
    if align is None:
        return None, None

    natural_align = 1 if uses_opaque_storage else (facts.natural_typed_align_bytes or 1)
    if align <= natural_align:
        return align, None
    if not _mojo_align_decorator_ok(align):
        return align, None
    return align, align


def _build_initializers(
    facts: RecordLayoutFacts,
    lowered_bitfield_groups: list[BitfieldGroupMember],
    *,
    uses_opaque_storage: bool,
) -> list[Initializer]:
    if uses_opaque_storage or not facts.is_pure_bitfield:
        return []

    named_members = [
        member
        for group in lowered_bitfield_groups
        for member in sorted(group.fields, key=lambda item: item.index)
    ]
    initializers = [Initializer(params=[])]
    if named_members:
        initializers.append(
            Initializer(
                params=[
                    InitializerParam(name=member.name, type=member.logical_type)
                    for member in named_members
                ]
            )
        )
    return initializers


def _incomplete_struct_decl(decl: Struct) -> StructDecl:
    return StructDecl(
        name=record_name(decl),
        kind=StructKind.OPAQUE,
        traits=[],
        align=None,
        align_decorator=None,
        fieldwise_init=False,
        members=[],
        initializers=[],
        diagnostics=[],
    )


def _opaque_storage_struct_decl(
    decl: Struct,
    facts: RecordLayoutFacts,
    *,
    diagnostic_notes: tuple[str, ...] = (),
    fallback_reasons: tuple[str, ...] = (),
) -> StructDecl:
    align, align_decorator = _compute_align_policy(facts, uses_opaque_storage=True)
    return StructDecl(
        name=record_name(decl),
        kind=StructKind.PLAIN,
        traits=[],
        align=align,
        align_decorator=align_decorator,
        fieldwise_init=False,
        members=[OpaqueStorageMember(name="storage", size_bytes=facts.size_bytes)],
        initializers=[],
        diagnostics=_build_diagnostics(
            facts.layout_problems,
            diagnostic_notes=diagnostic_notes,
            fallback_reasons=fallback_reasons,
        ),
    )


__all__ = [
    "StructLoweringContext",
    "StructLoweringError",
    "lower_struct",
]
