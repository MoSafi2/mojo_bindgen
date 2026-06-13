"""Map CIR unions into MojoIR union layout aliases."""

from __future__ import annotations

import json
from dataclasses import dataclass

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
    Array,
    BuiltinType,
    MojoBuiltin,
    NamedType,
    ParametricBase,
    ParametricType,
    Struct,
    Type,
    TypeArg,
)


class UnionMappingError(ValueError):
    """Raised when a CIR union declaration cannot be mapped to MojoIR."""


@dataclass(frozen=True)
class _UnionArmPlan:
    arms: tuple[Type, ...]
    diagnostics: tuple
    eligible: bool


@dataclass
class MapUnionPass:
    """Map top-level CIR union declarations to MojoIR alias declarations."""

    type_mapper: MapTypePass

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
        arms: list[Type] = []
        seen_keys: dict[str, str] = {}
        eligible = not diagnostics

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

            if isinstance(mapped, NamedType) and mapped.name == alias_name:
                eligible = False
                diagnostics.append(
                    union_note(
                        f"union member `{field_name}` mapped to self-referential type `{alias_name}`; using byte-storage fallback"
                    )
                )
                continue

            key = self._type_key(mapped)
            prior_name = seen_keys.get(key)
            if prior_name is not None:
                diagnostics.append(_duplicate_member_note(field_name, prior_name))
                continue

            seen_keys[key] = field_name
            arms.append(mapped)

        return _UnionArmPlan(arms=tuple(arms), diagnostics=tuple(diagnostics), eligible=eligible)

    @staticmethod
    def _type_key(t: Type) -> str:
        return json.dumps(t.to_json_dict(), sort_keys=True)


def _incomplete_union_alias(decl: Struct) -> AliasDecl:
    return AliasDecl(
        name=record_name(decl),
        kind=AliasKind.UNION_LAYOUT,
        diagnostics=[stub_note("incomplete union placeholder emitted; layout not mapped")],
        doc=decl.doc,
    )


def _unsafe_union_alias(decl: Struct, *, alias_name: str, plan: _UnionArmPlan) -> AliasDecl:
    return AliasDecl(
        name=alias_name,
        kind=AliasKind.UNION_LAYOUT,
        type_value=ParametricType(
            base=ParametricBase.UNSAFE_UNION,
            args=[TypeArg(type=arm) for arm in plan.arms],
        ),
        diagnostics=list(plan.diagnostics),
        doc=decl.doc,
    )


def _byte_storage_union_alias(decl: Struct, *, alias_name: str, plan: _UnionArmPlan) -> AliasDecl:
    return AliasDecl(
        name=alias_name,
        kind=AliasKind.UNION_LAYOUT,
        type_value=Array(
            element=BuiltinType(MojoBuiltin.UINT8),
            size=decl.size_bytes,
            array_kind="fixed",
        ),
        diagnostics=[
            *plan.diagnostics,
            union_note(
                f"union `{decl.c_name}` mapped as InlineArray[UInt8, {decl.size_bytes}] to preserve layout"
            ),
        ],
        doc=decl.doc,
    )


def _size_diagnostics(decl: Struct) -> list:
    if decl.size_bytes > 0:
        return []
    return [
        union_note(
            f"union `{decl.c_name}` has non-representable byte size {decl.size_bytes}; using byte-storage fallback"
        )
    ]


def _duplicate_member_note(field_name: str, prior_name: str):
    return union_note(
        f"union member `{field_name}` duplicates mapped type of earlier member `{prior_name}`;"
    )


def map_union(decl: Struct, *, type_mapper: MapTypePass | None = None) -> AliasDecl:
    """Map one top-level union declaration to a MojoIR alias."""

    return MapUnionPass(type_mapper=type_mapper or MapTypePass()).run(decl)


__all__ = [
    "MapUnionPass",
    "UnionMappingError",
    "map_union",
]
