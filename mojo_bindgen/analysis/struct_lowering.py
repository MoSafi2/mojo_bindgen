"""Lower CIR structs into MojoIR structs using pure layout facts plus Mojo planning."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

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
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, collect_type_nodes
from mojo_bindgen.ir import (
    Array,
    ArrayType,
    AtomicType,
    BitfieldField,
    BitfieldGroupMember,
    FlexibleTail,
    Initializer,
    InitializerParam,
    OpaqueStorageMember,
    PaddingMember,
    ParametricBase,
    ParametricType,
    QualifiedType,
    StoredMember,
    Struct,
    StructDecl,
    StructKind,
    StructRef,
    TargetABI,
    Type,
    TypeRef,
)


class StructLoweringError(ValueError):
    """Raised when a CIR struct declaration cannot be lowered to MojoIR."""


@dataclass
class StructLoweringContext:
    record_map: dict[str, Struct]
    target_abi: TargetABI
    type_lowerer: LowerTypePass
    by_value_typed_shape_cache: dict[str, _TypedRecordShape] = field(default_factory=dict)


@dataclass(frozen=True)
class _TypedRecordShape:
    valid: bool
    detail: tuple[str, ...] = ()
    flexible_tail: FlexibleTail | None = None


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
    plain_fields, lowered_bitfield_groups, flexible_tail, diagnostic_notes, fallback_reasons = (
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
        flexible_tail=flexible_tail,
        diagnostics=_build_diagnostics(
            facts.layout_problems,
            diagnostic_notes=diagnostic_notes,
            fallback_reasons=(),
        ),
        doc=decl.doc,
    )


def _lower_typed_members(
    decl: Struct,
    facts: RecordLayoutFacts,
    *,
    context: StructLoweringContext,
) -> tuple[
    list[StoredMember],
    list[BitfieldGroupMember],
    FlexibleTail | None,
    tuple[str, ...],
    tuple[str, ...],
]:
    plain_fields: list[StoredMember] = []
    lowered_bitfield_groups: list[BitfieldGroupMember] = []
    flexible_tail: FlexibleTail | None = None
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
                doc=field.doc,
            )
        )
        if field.fam_pattern is not None:
            flexible_tail, reason = _lower_flexible_tail_metadata(
                field,
                field_fact.index,
                field_fact.byte_offset,
                lowered_type,
            )
            if reason is not None:
                fallback_reasons.append(reason)
                flexible_tail = None
            continue

        refs = _embedded_struct_refs(field.type)
        if not refs:
            continue
        direct_ref = _direct_embedded_struct_ref(field.type)
        nested_tail_shapes: list[tuple[StructRef, _TypedRecordShape]] = []
        for ref in refs:
            shape = _record_typed_shape_by_value(
                ref.decl_id,
                context=context,
                active={decl.decl_id},
            )
            if not shape.valid:
                target_name = ref.c_name or ref.name
                suffix = (
                    shape.detail[0]
                    if shape.detail
                    else "embedded record is not layout-emittable by value"
                )
                fallback_reasons.append(
                    f"field `{display_name}` embeds struct `{target_name}` by value, but {suffix}; "
                    "opaque storage emitted"
                )
                break
            if shape.flexible_tail is not None:
                nested_tail_shapes.append((ref, shape))
        else:
            if not nested_tail_shapes:
                continue
            if len(nested_tail_shapes) > 1 or direct_ref is None:
                fallback_reasons.append(
                    f"field `{display_name}` embeds a flexible-tail record through a non-direct "
                    "aggregate type; opaque storage emitted"
                )
                continue
            nested_ref, nested_shape = nested_tail_shapes[0]
            if nested_ref.decl_id != direct_ref.decl_id:
                fallback_reasons.append(
                    f"field `{display_name}` embeds a flexible-tail record through a non-direct "
                    "aggregate type; opaque storage emitted"
                )
                continue
            if not _field_is_terminal_in_enclosing_record(facts, field_fact):
                target_name = nested_ref.c_name or nested_ref.name
                fallback_reasons.append(
                    f"field `{display_name}` embeds struct `{target_name}` by value, but embedded "
                    "flexible tail is not terminal in the enclosing record; opaque storage emitted"
                )
                continue
            flexible_tail = replace(
                nested_shape.flexible_tail,  # type: ignore
                byte_offset=field_fact.byte_offset + nested_shape.flexible_tail.byte_offset,  # type: ignore
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
                    doc=field_layout.field.doc,
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
        flexible_tail,
        tuple(diagnostic_notes),
        tuple(fallback_reasons),
    )


def _lower_flexible_tail_metadata(
    field,
    index: int,
    byte_offset: int,
    lowered_type,
) -> tuple[FlexibleTail | None, str | None]:
    if not isinstance(field.type, Array):
        return None, "flexible tail field did not lower from an array type; opaque storage emitted"
    if not isinstance(lowered_type, ArrayType) or lowered_type.count != 0:
        return (
            None,
            f"field `{field_display_name(field, index)}` did not lower to InlineArray[..., 0]; "
            "opaque storage emitted",
        )
    return (
        FlexibleTail(
            field_name=field.name,
            element_type=lowered_type.element,
            pattern=field.fam_pattern,
            byte_offset=byte_offset,
        ),
        None,
    )


def _record_typed_shape_by_value(
    decl_id: str,
    *,
    context: StructLoweringContext,
    active: set[str],
) -> _TypedRecordShape:
    cached = context.by_value_typed_shape_cache.get(decl_id)
    if cached is not None:
        return cached

    decl = context.record_map.get(decl_id)
    if decl is None:
        result = _TypedRecordShape(False, ("referenced definition is unavailable",))
        context.by_value_typed_shape_cache[decl_id] = result
        return result
    if decl.is_union:
        result = _TypedRecordShape(True)
        context.by_value_typed_shape_cache[decl_id] = result
        return result
    if not decl.is_complete:
        result = _TypedRecordShape(False, ("referenced definition is incomplete",))
        context.by_value_typed_shape_cache[decl_id] = result
        return result
    if decl_id in active:
        result = _TypedRecordShape(True)
        context.by_value_typed_shape_cache[decl_id] = result
        return result

    facts = analyze_record_layout(
        decl,
        record_map=context.record_map,
        target_abi=context.target_abi,
    )
    if not facts.is_complete:
        result = _TypedRecordShape(False, ("referenced definition is incomplete",))
        context.by_value_typed_shape_cache[decl_id] = result
        return result
    if facts.layout_problems:
        result = _TypedRecordShape(False, (facts.layout_problems[0],))
        context.by_value_typed_shape_cache[decl_id] = result
        return result

    active.add(decl_id)
    try:
        flexible_tail: FlexibleTail | None = None
        for field_fact in facts.plain_fields:
            field = decl.fields[field_fact.index]
            lowered_type, reason = try_lower_type(
                context.type_lowerer,
                field.type,
                subject=f"field `{field_display_name(field, field_fact.index)}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None or lowered_type is None:
                result = _TypedRecordShape(False, ((reason or "field could not be lowered"),))
                context.by_value_typed_shape_cache[decl_id] = result
                return result
            if field.fam_pattern is not None:
                direct_tail, tail_reason = _lower_flexible_tail_metadata(
                    field,
                    field_fact.index,
                    field_fact.byte_offset,
                    lowered_type,
                )
                if tail_reason is not None or direct_tail is None:
                    result = _TypedRecordShape(
                        False, ((tail_reason or "flexible tail could not lower"),)
                    )
                    context.by_value_typed_shape_cache[decl_id] = result
                    return result
                flexible_tail = direct_tail
                continue

            refs = _embedded_struct_refs(field.type)
            if not refs:
                continue
            direct_ref = _direct_embedded_struct_ref(field.type)
            nested_tail_shapes: list[tuple[StructRef, _TypedRecordShape]] = []
            for ref in refs:
                shape = _record_typed_shape_by_value(
                    ref.decl_id,
                    context=context,
                    active=active,
                )
                if not shape.valid:
                    result = _TypedRecordShape(False, shape.detail)
                    context.by_value_typed_shape_cache[decl_id] = result
                    return result
                if shape.flexible_tail is not None:
                    nested_tail_shapes.append((ref, shape))
            if not nested_tail_shapes:
                continue
            if len(nested_tail_shapes) > 1 or direct_ref is None:
                result = _TypedRecordShape(
                    False,
                    ("embedded flexible tail is not a direct terminal by-value struct field",),
                )
                context.by_value_typed_shape_cache[decl_id] = result
                return result
            nested_ref, nested_shape = nested_tail_shapes[0]
            if nested_ref.decl_id != direct_ref.decl_id:
                result = _TypedRecordShape(
                    False,
                    ("embedded flexible tail is not a direct terminal by-value struct field",),
                )
                context.by_value_typed_shape_cache[decl_id] = result
                return result
            if not _field_is_terminal_in_enclosing_record(facts, field_fact):
                result = _TypedRecordShape(
                    False,
                    ("embedded flexible tail is not terminal in the enclosing record",),
                )
                context.by_value_typed_shape_cache[decl_id] = result
                return result
            flexible_tail = replace(
                nested_shape.flexible_tail,  # type: ignore
                byte_offset=field_fact.byte_offset + nested_shape.flexible_tail.byte_offset,  # type: ignore
            )

        for run_layout in facts.bitfield_runs:
            _, reason = try_lower_type(
                context.type_lowerer,
                run_layout.unsigned_storage_type,
                subject=f"bitfield storage `{run_layout.name}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None:
                result = _TypedRecordShape(False, (reason,))
                context.by_value_typed_shape_cache[decl_id] = result
                return result

            for field_layout in run_layout.fields:
                _, reason = try_lower_type(
                    context.type_lowerer,
                    field_layout.logical_type,
                    subject=f"bitfield `{field_display_name(field_layout.field, field_layout.index)}`",
                    failure_suffix="opaque storage emitted",
                )
                if reason is not None:
                    result = _TypedRecordShape(False, (reason,))
                    context.by_value_typed_shape_cache[decl_id] = result
                    return result
    finally:
        active.remove(decl_id)

    result = _TypedRecordShape(True, flexible_tail=flexible_tail)
    context.by_value_typed_shape_cache[decl_id] = result
    return result


def _direct_embedded_struct_ref(t: Type) -> StructRef | None:
    while True:
        if isinstance(t, QualifiedType):
            t = t.unqualified
            continue
        if isinstance(t, TypeRef):
            t = t.canonical
            continue
        break
    if isinstance(t, StructRef) and not t.is_union:
        return t
    return None


def _field_is_terminal_in_enclosing_record(
    facts: RecordLayoutFacts,
    field_fact,
) -> bool:
    field_end = field_fact.byte_offset + field_fact.size_bytes
    if any(
        other.byte_offset >= field_end
        for other in facts.plain_fields
        if other.index != field_fact.index
    ):
        return False
    if any(run.byte_offset >= field_end for run in facts.bitfield_runs):
        return False
    return True


def _embedded_struct_refs(t: Type) -> tuple[StructRef, ...]:
    return tuple(
        node
        for node in collect_type_nodes(
            t,
            lambda node: isinstance(node, StructRef) and not node.is_union,
            options=TypeWalkOptions(
                descend_pointer=False,
                descend_function_ptr=False,
                descend_vector_element=True,
            ),
        )
        if isinstance(node, StructRef)
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
        doc=decl.doc,
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
        doc=decl.doc,
    )


__all__ = [
    "StructLoweringContext",
    "StructLoweringError",
    "lower_struct",
]
