"""Map CIR unions into MojoIR union layout aliases."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.facts.c_abi import CABIQueries
from mojo_bindgen.analysis.facts.context import AnalysisContext
from mojo_bindgen.analysis.facts.representation import contains_storage, storage_type, target_layout
from mojo_bindgen.analysis.facts.type_layout import peel_layout_wrappers
from mojo_bindgen.analysis.mojo.mapping_support import (
    field_display_name,
    record_name,
    stub_note,
    try_map_type,
    union_note,
)
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    MappingNote,
    MojoType,
    NamedType,
    ParametricBase,
    ParametricType,
    Struct,
    StructRef,
    TypeArg,
)


class UnionMappingError(ValueError):
    """Raised when a CIR union declaration cannot be mapped to MojoIR."""


@dataclass(frozen=True)
class _UnionArmPlan:
    arms: tuple[MojoType, ...]
    diagnostics: tuple[MappingNote, ...]
    eligible: bool


@dataclass
class MapUnionPass:
    """Map top-level CIR union declarations to MojoIR alias declarations."""

    type_mapper: MapTypePass
    context: AnalysisContext | None = None

    def run(self, decl: Struct) -> AliasDecl:
        if not decl.is_union:
            raise UnionMappingError(
                f"expected union Struct declaration, got non-union {decl.decl_id!r}"
            )

        if not decl.is_complete:
            return _incomplete_union_alias(decl)

        alias_name = record_name(decl)
        plan = self._collect_union_arms(decl, alias_name=alias_name)
        if plan.eligible:
            return _unsafe_union_alias(decl, alias_name=alias_name, plan=plan)
        return _byte_storage_union_alias(decl, alias_name=alias_name, plan=plan)

    def _collect_union_arms(self, decl: Struct, *, alias_name: str) -> _UnionArmPlan:
        diagnostics = _size_diagnostics(decl)
        arms: list[MojoType] = []
        seen_types: list[tuple[MojoType, str]] = []
        eligible = not diagnostics
        target_size, target_align = 0, 1

        for index, field in enumerate(decl.fields):
            field_name = field_display_name(field, index)
            mapped, reason = try_map_type(
                self.type_mapper,
                field.type,
                subject=f"union member `{field_name}`",
                failure_suffix="using byte-storage fallback",
            )
            if reason is not None or mapped is None:
                eligible = False
                if reason is not None:
                    diagnostics.append(union_note(reason))
                continue

            representation = self.type_mapper.run(peel_layout_wrappers(field.type))
            core = peel_layout_wrappers(field.type)
            if (
                isinstance(core, StructRef)
                and self.context is not None
                and CABIQueries(self.context).record(core.decl_id).eligible
            ):
                shape = self.context.record_storage[core.decl_id].target_layout
            else:
                shape = target_layout(representation, self.type_mapper.queries)
            if shape is None or contains_storage(representation):
                eligible = False
            else:
                target_size, target_align = max(target_size, shape[0]), max(target_align, shape[1])
            if isinstance(mapped, NamedType) and mapped.name == alias_name:
                eligible = False
                diagnostics.append(
                    union_note(
                        f"union member `{field_name}` mapped to self-referential type `{alias_name}`; using byte-storage fallback"
                    )
                )
                continue

            prior_name = next((name for prior, name in seen_types if prior == mapped), None)
            if prior_name is not None:
                diagnostics.append(_duplicate_member_note(field_name, prior_name))
                continue

            seen_types.append((mapped, field_name))
            arms.append(mapped)

        eligible = (
            eligible
            and bool(arms)
            and ((target_size + target_align - 1) // target_align) * target_align == decl.size_bytes
            and target_align == decl.align_bytes
        )
        return _UnionArmPlan(arms=tuple(arms), diagnostics=tuple(diagnostics), eligible=eligible)


def _incomplete_union_alias(decl: Struct) -> AliasDecl:
    return AliasDecl(
        name=record_name(decl),
        kind=AliasKind.UNION_LAYOUT,
        diagnostics=(stub_note("incomplete union placeholder emitted; layout not mapped"),),
        doc=decl.doc,
    )


def _unsafe_union_alias(decl: Struct, *, alias_name: str, plan: _UnionArmPlan) -> AliasDecl:
    return AliasDecl(
        name=alias_name,
        kind=AliasKind.UNION_LAYOUT,
        type_value=ParametricType(
            base=ParametricBase.UNSAFE_UNION,
            args=tuple(TypeArg(type=arm) for arm in plan.arms),
        ),
        diagnostics=plan.diagnostics,
        doc=decl.doc,
    )


def _byte_storage_union_alias(decl: Struct, *, alias_name: str, plan: _UnionArmPlan) -> AliasDecl:
    return AliasDecl(
        name=alias_name,
        kind=AliasKind.UNION_LAYOUT,
        type_value=storage_type(decl.size_bytes, decl.align_bytes),
        diagnostics=(
            *plan.diagnostics,
            union_note(
                f"union `{decl.c_name}` mapped as aligned opaque storage to preserve size and alignment"
            ),
        ),
        doc=decl.doc,
    )


def _size_diagnostics(decl: Struct) -> list[MappingNote]:
    if decl.size_bytes > 0:
        return []
    return [
        union_note(
            f"union `{decl.c_name}` has non-representable byte size {decl.size_bytes}; using byte-storage fallback"
        )
    ]


def _duplicate_member_note(field_name: str, prior_name: str) -> MappingNote:
    return union_note(
        f"union member `{field_name}` duplicates mapped type of earlier member `{prior_name}`;"
    )


def map_union(decl: Struct, *, type_mapper: MapTypePass) -> AliasDecl:
    """Map one top-level union declaration to a MojoIR alias."""

    return MapUnionPass(type_mapper=type_mapper).run(decl)


__all__ = [
    "MapUnionPass",
    "UnionMappingError",
    "map_union",
]
