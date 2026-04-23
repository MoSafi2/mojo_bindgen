"""Lower CIR structs into MojoIR structs using pure layout facts plus Mojo planning."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.bitfield_layout import bitfield_field_is_bool, bitfield_field_is_signed
from mojo_bindgen.analysis.common import _mojo_align_decorator_ok
from mojo_bindgen.analysis.lowering_support import (
    field_display_name,
    field_mojo_name,
    record_name,
    struct_note,
    try_lower_type,
)
from mojo_bindgen.analysis.record_layout import (
    AnalyzeRecordLayoutPass,
    RecordLayoutFacts,
)
from mojo_bindgen.analysis.type_lowering import LowerTypePass
from mojo_bindgen.ir import (
    AtomicType,
    Struct,
    TargetABI,
)
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


class LowerStructPass:
    """Lower one top-level CIR struct declaration into a MojoIR ``StructDecl``."""

    def __init__(self) -> None:
        self._analyze = AnalyzeRecordLayoutPass()

    def run(self, decl: Struct, *, context: StructLoweringContext) -> StructDecl:
        if decl.is_union:
            raise StructLoweringError(
                f"expected non-union Struct declaration, got union {decl.decl_id!r}"
            )

        facts = self._analyze.run(
            decl,
            record_map=context.record_map,
            target_abi=context.target_abi,
        )

        if not facts.is_complete:
            return self._incomplete_struct_decl(decl)
        if facts.layout_problems:
            return self._opaque_storage_struct_decl(decl, facts)

        plain_fields, bitfield_runs, diagnostic_notes, fallback_reasons = self._lower_typed_members(
            decl,
            facts,
            context=context,
        )
        if fallback_reasons:
            return self._opaque_storage_struct_decl(
                decl,
                facts,
                diagnostic_notes=diagnostic_notes,
                fallback_reasons=fallback_reasons,
            )

        align, align_decorator = self._compute_align_policy(facts, uses_opaque_storage=False)
        return StructDecl(
            name=record_name(decl),
            kind=StructKind.PLAIN,
            traits=[],
            align=align,
            align_decorator=align_decorator,
            fieldwise_init=False,
            members=self._build_members(decl, facts, plain_fields, bitfield_runs),
            initializers=self._build_initializers(
                facts,
                bitfield_runs,
                uses_opaque_storage=False,
            ),
            diagnostics=self._build_diagnostics(
                facts,
                diagnostic_notes=diagnostic_notes,
                fallback_reasons=(),
            ),
        )

    def _lower_typed_members(
        self,
        decl: Struct,
        facts: RecordLayoutFacts,
        *,
        context: StructLoweringContext,
    ) -> tuple[list[StoredMember], list[BitfieldGroupMember], tuple[str, ...], tuple[str, ...]]:
        plain_fields: list[StoredMember] = []
        bitfield_runs: list[BitfieldGroupMember] = []
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
                isinstance(lowered_type, ParametricType)
                and lowered_type.base == ParametricBase.ATOMIC
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

        for run in facts.bitfield_runs:
            lowered_storage_type, reason = try_lower_type(
                context.type_lowerer,
                run.unsigned_storage_type,
                subject=f"bitfield storage `{run.name}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None or lowered_storage_type is None:
                if reason is not None:
                    fallback_reasons.append(reason)
                continue

            lowered_fields: list[BitfieldField] = []
            for index in run.member_indexes:
                field = decl.fields[index]
                display_name = field_display_name(field, index)
                logical_type, reason = try_lower_type(
                    context.type_lowerer,
                    field.type,
                    subject=f"bitfield `{display_name}`",
                    failure_suffix="opaque storage emitted",
                )
                if reason is not None or logical_type is None:
                    if reason is not None:
                        fallback_reasons.append(reason)
                    continue
                lowered_fields.append(
                    BitfieldField(
                        index=index,
                        name=field_mojo_name(field, index),
                        logical_type=logical_type,
                        bit_offset=field.bit_offset,
                        bit_width=field.bit_width,
                        signed=bitfield_field_is_signed(field),
                        bool_semantics=bitfield_field_is_bool(field),
                    )
                )

            bitfield_runs.append(
                BitfieldGroupMember(
                    storage_name=run.name,
                    storage_type=lowered_storage_type,
                    byte_offset=run.byte_offset,
                    first_index=run.first_index,
                    fields=lowered_fields,
                )
            )

        return (
            plain_fields,
            bitfield_runs,
            tuple(diagnostic_notes),
            tuple(fallback_reasons),
        )

    def _build_members(
        self,
        decl: Struct,
        facts: RecordLayoutFacts,
        plain_fields: list[StoredMember],
        bitfield_runs: list[BitfieldGroupMember],
    ) -> list[StoredMember | PaddingMember | OpaqueStorageMember | BitfieldGroupMember]:
        members_with_offsets: list[
            tuple[
                int,
                int,
                StoredMember | PaddingMember | OpaqueStorageMember | BitfieldGroupMember,
            ]
        ] = [(field.byte_offset, field.index, field) for field in plain_fields]

        if not facts.is_pure_bitfield:
            pad_order_base = len(decl.fields) + len(bitfield_runs)
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

        for run in bitfield_runs:
            members_with_offsets.append((run.byte_offset, run.first_index, run))

        members_with_offsets.sort(key=lambda item: (item[0], item[1]))
        return [member for _, _, member in members_with_offsets]

    def _build_diagnostics(
        self,
        facts: RecordLayoutFacts,
        *,
        diagnostic_notes: tuple[str, ...],
        fallback_reasons: tuple[str, ...],
    ) -> list:
        return [
            *(
                struct_note(f"{problem}; opaque storage emitted")
                for problem in facts.layout_problems
            ),
            *(struct_note(note) for note in diagnostic_notes),
            *(struct_note(reason) for reason in fallback_reasons),
        ]

    def _compute_align_policy(
        self,
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
        self,
        facts: RecordLayoutFacts,
        bitfield_runs: list[BitfieldGroupMember],
        *,
        uses_opaque_storage: bool,
    ) -> list[Initializer]:
        if uses_opaque_storage or not facts.is_pure_bitfield:
            return []

        named_members = [
            member
            for run in bitfield_runs
            for member in sorted(run.fields, key=lambda item: item.index)
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

    def _incomplete_struct_decl(self, decl: Struct) -> StructDecl:
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
        self,
        decl: Struct,
        facts: RecordLayoutFacts,
        *,
        diagnostic_notes: tuple[str, ...] = (),
        fallback_reasons: tuple[str, ...] = (),
    ) -> StructDecl:
        align, align_decorator = self._compute_align_policy(facts, uses_opaque_storage=True)
        return StructDecl(
            name=record_name(decl),
            kind=StructKind.PLAIN,
            traits=[],
            align=align,
            align_decorator=align_decorator,
            fieldwise_init=False,
            members=[OpaqueStorageMember(name="storage", size_bytes=facts.size_bytes)],
            initializers=[],
            diagnostics=self._build_diagnostics(
                facts,
                diagnostic_notes=diagnostic_notes,
                fallback_reasons=fallback_reasons,
            ),
        )


def lower_struct(decl: Struct, *, context: StructLoweringContext) -> StructDecl:
    """Lower one top-level CIR struct declaration to MojoIR."""

    return LowerStructPass().run(decl, context=context)


__all__ = [
    "LowerStructPass",
    "StructLoweringContext",
    "StructLoweringError",
    "lower_struct",
]
