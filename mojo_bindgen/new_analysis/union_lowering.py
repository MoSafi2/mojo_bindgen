"""Lower CIR unions into MojoIR union layout aliases."""

from __future__ import annotations

import json
from dataclasses import dataclass

from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.ir import Field, Struct
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BuiltinType,
    LoweringNote,
    LoweringSeverity,
    MojoBuiltin,
    MojoType,
    NamedType,
    ParametricBase,
    ParametricType,
    TypeArg,
)
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass, TypeLoweringError


class UnionLoweringError(ValueError):
    """Raised when a CIR union declaration cannot be lowered to MojoIR."""


def _union_name(decl: Struct) -> str:
    raw_name = decl.name.strip() or decl.c_name.strip()
    return mojo_ident(raw_name, fallback="anonymous_union")


def _field_display_name(field: Field, index: int) -> str:
    if field.source_name:
        return field.source_name
    if field.name:
        return field.name
    return f"field_{index}"


def _union_note(message: str) -> LoweringNote:
    return LoweringNote(
        severity=LoweringSeverity.NOTE,
        message=message,
        category="union_lowering",
    )


def _stub_note(message: str) -> LoweringNote:
    return LoweringNote(
        severity=LoweringSeverity.NOTE,
        message=message,
        category="stub_lowering",
    )


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
                name=_union_name(decl),
                kind=AliasKind.UNION_LAYOUT,
                diagnostics=[
                    _stub_note("incomplete union placeholder emitted; layout not lowered")
                ],
            )

        alias_name = _union_name(decl)
        diagnostics: list[LoweringNote] = []
        arms: list[MojoType] = []
        seen_keys: dict[str, str] = {}
        eligible = True

        if decl.size_bytes <= 0:
            eligible = False
            diagnostics.append(
                _union_note(
                    f"union `{decl.c_name}` has non-representable byte size {decl.size_bytes}; using byte-storage fallback"
                )
            )

        for index, field in enumerate(decl.fields):
            field_name = _field_display_name(field, index)
            try:
                lowered = self.type_lowerer.run(field.type)
            except TypeLoweringError as exc:
                eligible = False
                diagnostics.append(
                    _union_note(
                        f"union member `{field_name}` could not be lowered ({exc}); using byte-storage fallback"
                    )
                )
                continue

            if lowered == BuiltinType(MojoBuiltin.UNSUPPORTED):
                eligible = False
                diagnostics.append(
                    _union_note(
                        f"union member `{field_name}` lowered to unsupported type; using byte-storage fallback"
                    )
                )
                continue

            if isinstance(lowered, NamedType) and lowered.name == alias_name:
                eligible = False
                diagnostics.append(
                    _union_note(
                        f"union member `{field_name}` lowered to self-referential type `{alias_name}`; using byte-storage fallback"
                    )
                )
                continue

            key = self._type_key(lowered)
            prior_name = seen_keys.get(key)
            if prior_name is not None:
                eligible = False
                diagnostics.append(
                    _union_note(
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
            diagnostics=diagnostics,
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
