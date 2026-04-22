"""Lower CIR structs into MojoIR structs using pure layout facts plus Mojo planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.analysis.common import _mojo_align_decorator_ok, field_mojo_name
from mojo_bindgen.ir import AtomicType, Struct, TargetABI
from mojo_bindgen.mojo_ir import (
    BitfieldField,
    BitfieldGroupMember,
    Initializer,
    InitializerParam,
    MojoType,
    OpaqueStorageMember,
    PaddingMember,
    ParametricBase,
    ParametricType,
    StoredMember,
    StructDecl,
    StructKind,
    StructTraits,
)
from mojo_bindgen.new_analysis.lowering_support import (
    field_display_name,
    record_name,
    struct_note,
    try_lower_type,
)
from mojo_bindgen.new_analysis.record_layout import AnalyzeRecordLayoutPass, RecordLayoutFacts
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass

RepresentationMode = Literal[
    "fieldwise_exact",
    "fieldwise_padded_exact",
    "opaque_storage_exact",
    "bitfield_exact",
]


class StructLoweringError(ValueError):
    """Raised when a CIR struct declaration cannot be lowered to MojoIR."""


@dataclass(frozen=True, init=False)
class StructLoweringContext:
    record_map: dict[str, Struct]
    register_passable_by_decl_id: dict[str, bool]
    target_abi: TargetABI
    type_lowerer: LowerTypePass

    def __init__(
        self,
        *,
        record_map: dict[str, Struct] | None = None,
        register_passable_by_decl_id: dict[str, bool],
        target_abi: TargetABI,
        type_lowerer: LowerTypePass,
        struct_map: dict[str, Struct] | None = None,
    ) -> None:
        resolved_record_map = record_map if record_map is not None else struct_map
        if resolved_record_map is None:
            raise TypeError("StructLoweringContext requires `record_map`")
        object.__setattr__(self, "record_map", resolved_record_map)
        object.__setattr__(
            self,
            "register_passable_by_decl_id",
            register_passable_by_decl_id,
        )
        object.__setattr__(self, "target_abi", target_abi)
        object.__setattr__(self, "type_lowerer", type_lowerer)

    @property
    def struct_map(self) -> dict[str, Struct]:
        return self.record_map


@dataclass(frozen=True)
class LoweredPlainField:
    index: int
    mojo_name: str
    lowered_type: MojoType
    byte_offset: int


@dataclass(frozen=True)
class LoweredBitfieldMember:
    index: int
    mojo_name: str
    logical_type: MojoType
    bit_offset: int
    bit_width: int
    signed: bool
    bool_semantics: bool

    def as_mojo_field(self) -> BitfieldField:
        return BitfieldField(
            name=self.mojo_name,
            logical_type=self.logical_type,
            bit_offset=self.bit_offset,
            bit_width=self.bit_width,
            signed=self.signed,
            bool_semantics=self.bool_semantics,
        )


@dataclass(frozen=True)
class LoweredBitfieldRun:
    name: str
    first_index: int
    byte_offset: int
    lowered_storage_type: MojoType
    members: tuple[LoweredBitfieldMember, ...]


@dataclass(frozen=True)
class StructRepresentationPlan:
    representation_mode: RepresentationMode
    plain_fields: tuple[LoweredPlainField, ...]
    bitfield_runs: tuple[LoweredBitfieldRun, ...]
    diagnostic_notes: tuple[str, ...]
    fallback_reasons: tuple[str, ...]


@dataclass(frozen=True)
class StructBodyPlan:
    members: list[StoredMember | PaddingMember | OpaqueStorageMember | BitfieldGroupMember]


class PlanStructRepresentationPass:
    """Lower pure layout facts into a Mojo-facing representation plan."""

    def run(
        self,
        facts: RecordLayoutFacts,
        *,
        context: StructLoweringContext,
    ) -> StructRepresentationPlan:
        if not facts.is_complete:
            return StructRepresentationPlan(
                representation_mode="fieldwise_exact",
                plain_fields=(),
                bitfield_runs=(),
                diagnostic_notes=(),
                fallback_reasons=(),
            )

        if facts.layout_problems:
            return StructRepresentationPlan(
                representation_mode="opaque_storage_exact",
                plain_fields=(),
                bitfield_runs=(),
                diagnostic_notes=(),
                fallback_reasons=(),
            )

        plain_fields, plain_notes, plain_reasons = self._lower_plain_fields(facts, context=context)
        bitfield_runs, bitfield_reasons = self._lower_bitfield_runs(facts, context=context)
        fallback_reasons = tuple([*plain_reasons, *bitfield_reasons])
        diagnostic_notes = tuple(plain_notes)

        if fallback_reasons:
            return StructRepresentationPlan(
                representation_mode="opaque_storage_exact",
                plain_fields=(),
                bitfield_runs=(),
                diagnostic_notes=diagnostic_notes,
                fallback_reasons=fallback_reasons,
            )
        if bitfield_runs:
            return StructRepresentationPlan(
                representation_mode="bitfield_exact",
                plain_fields=tuple(plain_fields),
                bitfield_runs=tuple(bitfield_runs),
                diagnostic_notes=diagnostic_notes,
                fallback_reasons=(),
            )
        if facts.padding_spans:
            return StructRepresentationPlan(
                representation_mode="fieldwise_padded_exact",
                plain_fields=tuple(plain_fields),
                bitfield_runs=(),
                diagnostic_notes=diagnostic_notes,
                fallback_reasons=(),
            )
        return StructRepresentationPlan(
            representation_mode="fieldwise_exact",
            plain_fields=tuple(plain_fields),
            bitfield_runs=(),
            diagnostic_notes=diagnostic_notes,
            fallback_reasons=(),
        )

    def _lower_plain_fields(
        self,
        facts: RecordLayoutFacts,
        *,
        context: StructLoweringContext,
    ) -> tuple[list[LoweredPlainField], list[str], list[str]]:
        lowered: list[LoweredPlainField] = []
        notes: list[str] = []
        reasons: list[str] = []
        for field_fact in facts.plain_fields:
            field = field_fact.field
            display_name = field_display_name(field, field_fact.index)
            lowered_type, reason = try_lower_type(
                context.type_lowerer,
                field.type,
                subject=f"field `{display_name}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None or lowered_type is None:
                if reason is not None:
                    reasons.append(reason)
                continue
            if isinstance(field.type, AtomicType) and not (
                isinstance(lowered_type, ParametricType)
                and lowered_type.base == ParametricBase.ATOMIC
            ):
                note = (
                    "some atomic types were mapped to their underlying non-atomic Mojo type "
                    "because Atomic[dtype] was not representable"
                )
                if note not in notes:
                    notes.append(note)
            lowered.append(
                LoweredPlainField(
                    index=field_fact.index,
                    mojo_name=field_mojo_name(field, field_fact.index),
                    lowered_type=lowered_type,
                    byte_offset=field_fact.byte_offset,
                )
            )
        return lowered, notes, reasons

    def _lower_bitfield_runs(
        self,
        facts: RecordLayoutFacts,
        *,
        context: StructLoweringContext,
    ) -> tuple[list[LoweredBitfieldRun], list[str]]:
        lowered: list[LoweredBitfieldRun] = []
        reasons: list[str] = []

        for run in facts.bitfield_runs:
            lowered_storage_type, reason = try_lower_type(
                context.type_lowerer,
                run.unsigned_storage_type,
                subject=f"bitfield storage `{run.name}`",
                failure_suffix="opaque storage emitted",
            )
            if reason is not None or lowered_storage_type is None:
                if reason is not None:
                    reasons.append(reason)
                continue

            lowered_members: list[LoweredBitfieldMember] = []
            for member in run.members:
                field = member.field
                display_name = field_display_name(field, member.index)
                logical_type, reason = try_lower_type(
                    context.type_lowerer,
                    field.type,
                    subject=f"bitfield `{display_name}`",
                    failure_suffix="opaque storage emitted",
                )
                if reason is not None or logical_type is None:
                    if reason is not None:
                        reasons.append(reason)
                    continue
                lowered_members.append(
                    LoweredBitfieldMember(
                        index=member.index,
                        mojo_name=field_mojo_name(field, member.index),
                        logical_type=logical_type,
                        bit_offset=member.bit_offset,
                        bit_width=member.bit_width,
                        signed=member.signed,
                        bool_semantics=member.bool_semantics,
                    )
                )

            lowered.append(
                LoweredBitfieldRun(
                    name=run.name,
                    first_index=run.first_index,
                    byte_offset=run.byte_offset,
                    lowered_storage_type=lowered_storage_type,
                    members=tuple(lowered_members),
                )
            )

        return lowered, reasons


class LowerStructBodyPass:
    """Materialize MojoIR members from a representation plan plus pure layout facts."""

    def run(self, facts: RecordLayoutFacts, *, plan: StructRepresentationPlan) -> StructBodyPlan:
        if not facts.is_complete:
            return StructBodyPlan(members=[])
        if plan.representation_mode == "opaque_storage_exact":
            return StructBodyPlan(
                members=[OpaqueStorageMember(name="storage", size_bytes=facts.size_bytes)]
            )

        members_with_offsets: list[
            tuple[
                int, int, StoredMember | PaddingMember | OpaqueStorageMember | BitfieldGroupMember
            ]
        ] = []
        for field in plan.plain_fields:
            members_with_offsets.append(
                (
                    field.byte_offset,
                    field.index,
                    StoredMember(
                        name=field.mojo_name,
                        type=field.lowered_type,
                        byte_offset=field.byte_offset,
                    ),
                )
            )

        emit_padding = not facts.is_pure_bitfield
        if emit_padding:
            pad_order_base = len(facts.decl.fields) + len(plan.bitfield_runs)
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

        for run in plan.bitfield_runs:
            members_with_offsets.append(
                (
                    run.byte_offset,
                    run.first_index,
                    BitfieldGroupMember(
                        storage_name=run.name,
                        storage_type=run.lowered_storage_type,
                        byte_offset=run.byte_offset,
                        fields=[member.as_mojo_field() for member in run.members],
                    ),
                )
            )

        members_with_offsets.sort(key=lambda item: (item[0], item[1]))
        return StructBodyPlan(members=[member for _, _, member in members_with_offsets])


class FinalizeStructDeclPass:
    """Assemble the final MojoIR ``StructDecl`` from facts and a lowering plan."""

    def run(
        self,
        facts: RecordLayoutFacts,
        *,
        plan: StructRepresentationPlan,
        body_plan: StructBodyPlan,
        context: StructLoweringContext,
    ) -> StructDecl:
        diagnostics = [
            *(
                struct_note(f"{problem}; opaque storage emitted")
                for problem in facts.layout_problems
            ),
            *(struct_note(note) for note in plan.diagnostic_notes),
            *(struct_note(reason) for reason in plan.fallback_reasons),
        ]
        align, align_decorator = self._align_policy(facts, plan=plan)
        fieldwise_init = self._fieldwise_init_policy(facts, plan=plan)
        initializers = self._initializers(facts, plan=plan)
        traits = self._traits(facts, plan=plan, context=context)

        return StructDecl(
            name=record_name(facts.decl),
            kind=StructKind.OPAQUE if not facts.is_complete else StructKind.PLAIN,
            traits=traits,
            align=align,
            align_decorator=align_decorator,
            fieldwise_init=fieldwise_init,
            members=body_plan.members,
            initializers=initializers,
            diagnostics=diagnostics,
        )

    def _align_policy(
        self,
        facts: RecordLayoutFacts,
        *,
        plan: StructRepresentationPlan,
    ) -> tuple[int | None, int | None]:
        if not facts.is_complete:
            return None, None

        align = facts.decl.align_bytes
        natural_align = facts.natural_typed_align_bytes or 1
        if plan.representation_mode == "opaque_storage_exact":
            natural_align = 1

        if align <= natural_align:
            return align, None
        if not _mojo_align_decorator_ok(align):
            return align, None
        return align, align

    def _fieldwise_init_policy(
        self,
        facts: RecordLayoutFacts,
        *,
        plan: StructRepresentationPlan,
    ) -> bool:
        if not facts.is_complete:
            return False
        if plan.representation_mode == "opaque_storage_exact":
            return False
        if facts.has_representable_atomic_storage:
            return False
        if facts.is_pure_bitfield:
            return False
        return True

    def _initializers(
        self,
        facts: RecordLayoutFacts,
        *,
        plan: StructRepresentationPlan,
    ) -> list[Initializer]:
        if (
            not facts.is_complete
            or plan.representation_mode == "opaque_storage_exact"
            or not facts.is_pure_bitfield
        ):
            return []

        named_members = [
            member
            for run in plan.bitfield_runs
            for member in sorted(run.members, key=lambda item: item.index)
        ]
        initializers = [Initializer(params=[])]
        if named_members:
            initializers.append(
                Initializer(
                    params=[
                        InitializerParam(name=member.mojo_name, type=member.logical_type)
                        for member in named_members
                    ]
                )
            )
        return initializers

    def _traits(
        self,
        facts: RecordLayoutFacts,
        *,
        plan: StructRepresentationPlan,
        context: StructLoweringContext,
    ) -> list[StructTraits]:
        if facts.has_representable_atomic_storage:
            return []

        traits = [StructTraits.COPYABLE, StructTraits.MOVABLE]
        if (
            facts.is_complete
            and context.register_passable_by_decl_id.get(facts.decl.decl_id, False)
            and plan.representation_mode == "fieldwise_exact"
        ):
            traits.append(StructTraits.REGISTER_PASSABLE)
        return traits


class LowerStructPass:
    """Lower one top-level CIR struct declaration into a MojoIR ``StructDecl``."""

    def __init__(self) -> None:
        self._analyze = AnalyzeRecordLayoutPass()
        self._plan_representation = PlanStructRepresentationPass()
        self._lower_body = LowerStructBodyPass()
        self._finalize = FinalizeStructDeclPass()

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
        plan = self._plan_representation.run(facts, context=context)
        body_plan = self._lower_body.run(facts, plan=plan)
        return self._finalize.run(facts, plan=plan, body_plan=body_plan, context=context)


def lower_struct(decl: Struct, *, context: StructLoweringContext) -> StructDecl:
    """Lower one top-level CIR struct declaration to MojoIR."""

    return LowerStructPass().run(decl, context=context)


__all__ = [
    "LowerStructPass",
    "StructLoweringContext",
    "StructLoweringError",
    "lower_struct",
]
