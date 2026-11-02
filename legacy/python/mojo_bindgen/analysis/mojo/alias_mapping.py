"""Shared helpers for mapping typedef-like aliases into MojoIR."""

from __future__ import annotations

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass, exact_width_stdint_alias_type
from mojo_bindgen.ir import (
    _SIGNED_INT_KINDS,
    _UNSIGNED_INT_KINDS,
    AliasDecl,
    AliasKind,
    BuiltinType,
    CFunctionPtr,
    CType,
    DocComment,
    IntType,
    MojoBuiltin,
    MojoFunctionPtr,
    MojoType,
    NamedType,
)

from ..facts.representation import target_layout
from ..facts.type_layout import peel_layout_wrappers, type_layout
from .mapping_support import stub_note


def is_named_type(t: MojoType, name: str) -> bool:
    """Return whether ``t`` is exactly the Mojo named type ``name``."""

    return isinstance(t, NamedType) and t.name == name


def _integer_alias(name: str, t: CType) -> bool:
    core = peel_layout_wrappers(t)
    return isinstance(core, IntType) and (
        (core.int_kind in _SIGNED_INT_KINDS and name.startswith("Int"))
        or (core.int_kind in _UNSIGNED_INT_KINDS and name.startswith("UInt"))
    )


def map_typedef_alias(
    *,
    c_name: str,
    aliased: CType,
    type_mapper: MapTypePass,
    doc: DocComment | None = None,
) -> AliasDecl | None:
    """Map a C typedef-like alias, skipping no-op aliases to the same name."""

    alias_name = mojo_ident(c_name)
    mapped_type = exact_width_stdint_alias_type(c_name)
    if (
        mapped_type is None
        or not _integer_alias(mapped_type.name, aliased)
        or type_layout(aliased) != target_layout(mapped_type, type_mapper.queries)
    ):
        mapped_type = type_mapper.run(aliased)
    if isinstance(mapped_type, BuiltinType) and mapped_type.name == MojoBuiltin.UNSUPPORTED:
        return AliasDecl(
            alias_name,
            AliasKind.TYPE_ALIAS,
            diagnostics=(stub_note("alias type has no supported storage representation"),),
            doc=doc,
        )
    if isinstance(mapped_type, MojoFunctionPtr):
        return AliasDecl(
            name=alias_name,
            kind=AliasKind.CALLBACK_SIGNATURE,
            type_value=mapped_type,
            doc=doc,
        )
    if is_named_type(mapped_type, alias_name):
        return None
    return AliasDecl(
        name=alias_name,
        kind=AliasKind.TYPE_ALIAS,
        type_value=mapped_type,
        diagnostics=(stub_note("callback signature is unsupported; opaque address emitted"),)
        if isinstance(aliased, CFunctionPtr)
        else (),
        doc=doc,
    )


__all__ = [
    "is_named_type",
    "map_typedef_alias",
]
