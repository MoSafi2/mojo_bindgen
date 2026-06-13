"""Typedef and alias classification for normalized CIR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from mojo_bindgen.analysis.mojo.type_mapping import exact_width_stdint_alias_type
from mojo_bindgen.analysis.traversal import iter_unit_typerefs
from mojo_bindgen.ir import (
    EnumRef,
    FunctionPtr,
    StructRef,
    Type,
    Typedef,
    TypeRef,
    Unit,
)


class AliasClass(StrEnum):
    """Semantic classes for C typedef-like declarations and references."""

    CALLBACK = "callback"
    ENUM = "enum"
    EXACT_WIDTH_STDINT = "exact_width_stdint"
    EXTERNAL_TYPEDEF = "external_typedef"
    NO_OP_SELF_ALIAS = "no_op_self_alias"
    RECORD = "record"
    TYPEDEF = "typedef"


@dataclass(frozen=True)
class AliasInfo:
    """Classification for one typedef declaration or external typedef reference."""

    decl_id: str
    name: str
    alias_class: AliasClass
    target_decl_id: str | None = None


@dataclass(frozen=True)
class AliasClassification:
    """Alias classifications keyed by declaration id."""

    aliases_by_decl_id: dict[str, AliasInfo]
    external_aliases_by_decl_id: dict[str, AliasInfo]
    external_type_refs_by_decl_id: dict[str, TypeRef]


def classify_aliases(unit: Unit) -> AliasClassification:
    """Classify local typedef declarations and external typedef references."""

    local_typedefs = {decl.decl_id for decl in unit.decls if isinstance(decl, Typedef)}
    aliases = {
        decl.decl_id: AliasInfo(
            decl_id=decl.decl_id,
            name=decl.name,
            alias_class=_classify_typedef(decl),
            target_decl_id=_target_decl_id(decl.aliased) or _target_decl_id(decl.canonical),
        )
        for decl in unit.decls
        if isinstance(decl, Typedef)
    }

    external: dict[str, AliasInfo] = {}
    external_refs: dict[str, TypeRef] = {}
    for ref in iter_unit_typerefs(unit):
        if ref.decl_id in local_typedefs or ref.decl_id in external:
            continue
        external[ref.decl_id] = AliasInfo(
            decl_id=ref.decl_id,
            name=ref.name,
            alias_class=AliasClass.EXTERNAL_TYPEDEF,
            target_decl_id=_target_decl_id(ref.canonical),
        )
        external_refs[ref.decl_id] = ref

    return AliasClassification(
        aliases_by_decl_id=aliases,
        external_aliases_by_decl_id=external,
        external_type_refs_by_decl_id=external_refs,
    )


def _classify_typedef(decl: Typedef) -> AliasClass:
    if exact_width_stdint_alias_type(decl.name) is not None:
        return AliasClass.EXACT_WIDTH_STDINT
    if isinstance(decl.aliased, FunctionPtr) or isinstance(decl.canonical, FunctionPtr):
        return AliasClass.CALLBACK
    target = _target_type(decl.aliased) or _target_type(decl.canonical)
    if isinstance(target, EnumRef):
        return AliasClass.ENUM
    if isinstance(target, StructRef):
        return AliasClass.RECORD
    if isinstance(decl.aliased, TypeRef) and decl.aliased.decl_id == decl.decl_id:
        return AliasClass.NO_OP_SELF_ALIAS
    return AliasClass.TYPEDEF


def _target_type(t: Type) -> EnumRef | StructRef | None:
    if isinstance(t, TypeRef):
        return _target_type(t.canonical)
    if isinstance(t, (EnumRef, StructRef)):
        return t
    return None


def _target_decl_id(t: Type) -> str | None:
    target = _target_type(t)
    return None if target is None else target.decl_id


__all__ = [
    "AliasClass",
    "AliasClassification",
    "AliasInfo",
    "classify_aliases",
]
