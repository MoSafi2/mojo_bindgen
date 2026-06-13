"""Shared helpers for mapping typedef-like aliases into MojoIR."""

from __future__ import annotations

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass, exact_width_stdint_alias_type
from mojo_bindgen.ir import AliasDecl, AliasKind, DocComment, FunctionPtr, NamedType, Type


def is_named_type(t: Type, name: str) -> bool:
    """Return whether ``t`` is exactly the Mojo named type ``name``."""

    return isinstance(t, NamedType) and t.name == name


def map_typedef_alias(
    *,
    c_name: str,
    aliased: Type,
    type_mapper: MapTypePass,
    doc: DocComment | None = None,
) -> AliasDecl | None:
    """Map a C typedef-like alias, skipping no-op aliases to the same name."""

    alias_name = mojo_ident(c_name)
    mapped_type = exact_width_stdint_alias_type(c_name)
    if mapped_type is None:
        mapped_type = type_mapper.run(aliased)
    if isinstance(mapped_type, FunctionPtr):
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
        doc=doc,
    )


__all__ = [
    "is_named_type",
    "map_typedef_alias",
]
