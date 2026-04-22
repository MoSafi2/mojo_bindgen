"""Lower CIR unions into MojoIR union layout aliases."""

from __future__ import annotations

import json
from dataclasses import dataclass

from mojo_bindgen.ir import Struct
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BuiltinType,
    MojoBuiltin,
    MojoType,
    NamedType,
    ParametricBase,
    ParametricType,
    TypeArg,
)
from mojo_bindgen.new_analysis.lowering_support import (
    field_display_name,
    record_name,
    stub_note,
    try_lower_type,
    union_note,
)
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass


class UnionLoweringError(ValueError):
    """Raised when a CIR union declaration cannot be lowered to MojoIR."""


@dataclass
class LowerUnionPass:
    """Lower top-level CIR union declarations to MojoIR alias declarations."""

    type_lowerer: LowerTypePass

    def run(self, decl: Struct) -> AliasDecl:
        if not decl.is_union:
            raise UnionLoweringError(
                f"expected union Struct declaration, got non-union {decl.decl_id!r}"
            )

        if not decl.is_complete:
            return AliasDecl(
                name=record_name(decl),
                kind=AliasKind.UNION_LAYOUT,
                diagnostics=[stub_note("incomplete union placeholder emitted; layout not lowered")],
            )

        alias_name = record_name(decl)
        diagnostics = []
        arms: list[MojoType] = []
        seen_keys: dict[str, str] = {}
        eligible = True

        if decl.size_bytes <= 0:
            eligible = False
            diagnostics.append(
                union_note(
                    f"union `{decl.c_name}` has non-representable byte size {decl.size_bytes}; using byte-storage fallback"
                )
            )

        for index, field in enumerate(decl.fields):
            field_name = field_display_name(field, index)
            lowered, reason = try_lower_type(
                self.type_lowerer,
                field.type,
                subject=f"union member `{field_name}`",
                failure_suffix="using byte-storage fallback",
            )
            if reason is not None or lowered is None:
                eligible = False
                if reason is not None:
                    diagnostics.append(union_note(reason))
                continue

            if isinstance(lowered, NamedType) and lowered.name == alias_name:
                eligible = False
                diagnostics.append(
                    union_note(
                        f"union member `{field_name}` lowered to self-referential type `{alias_name}`; using byte-storage fallback"
                    )
                )
                continue

            key = self._type_key(lowered)
            prior_name = seen_keys.get(key)
            if prior_name is not None:
                eligible = False
                diagnostics.append(
                    union_note(
                        f"union member `{field_name}` duplicates lowered type of earlier member `{prior_name}`; using byte-storage fallback"
                    )
                )
                continue

            seen_keys[key] = field_name
            arms.append(lowered)

        if eligible:
            return AliasDecl(
                name=alias_name,
                kind=AliasKind.UNION_LAYOUT,
                type_value=ParametricType(
                    base=ParametricBase.UNSAFE_UNION,
                    args=[TypeArg(type=arm) for arm in arms],
                ),
            )

        return AliasDecl(
            name=alias_name,
            kind=AliasKind.UNION_LAYOUT,
            type_value=ArrayType(
                element=BuiltinType(MojoBuiltin.UINT8),
                count=decl.size_bytes,
            ),
            diagnostics=[
                *diagnostics,
                union_note(
                    f"union `{decl.c_name}` lowered as InlineArray[UInt8, {decl.size_bytes}] to preserve layout"
                ),
            ],
        )

    @staticmethod
    def _type_key(t: MojoType) -> str:
        return json.dumps(t.to_json_dict(), sort_keys=True)


def lower_union(decl: Struct, *, type_lowerer: LowerTypePass | None = None) -> AliasDecl:
    """Lower one top-level union declaration to a MojoIR alias."""

    return LowerUnionPass(type_lowerer=type_lowerer or LowerTypePass()).run(decl)


__all__ = [
    "LowerUnionPass",
    "UnionLoweringError",
    "lower_union",
]
