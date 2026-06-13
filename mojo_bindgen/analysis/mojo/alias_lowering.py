"""Shared helpers for lowering typedef-like aliases into MojoIR."""

from __future__ import annotations

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.mojo.type_lowering import LowerTypePass, exact_width_stdint_alias_type
from mojo_bindgen.ir import AliasDecl, AliasKind, DocComment, FunctionPtr, NamedType, Type


def is_named_type(t: Type, name: str) -> bool:
    """Return whether ``t`` is exactly the Mojo named type ``name``."""

    return isinstance(t, NamedType) and t.name == name


def lower_typedef_alias(
    *,
    c_name: str,
    aliased: Type,
    type_lowerer: LowerTypePass,
    doc: DocComment | None = None,
) -> AliasDecl | None:
    """Lower a C typedef-like alias, skipping no-op aliases to the same name."""

    alias_name = mojo_ident(c_name)
    lowered_type = exact_width_stdint_alias_type(c_name)
    if lowered_type is None:
        lowered_type = type_lowerer.run(aliased)
    if isinstance(lowered_type, FunctionPtr):
        return AliasDecl(
            name=alias_name,
            kind=AliasKind.CALLBACK_SIGNATURE,
            type_value=lowered_type,
            doc=doc,
        )
    if is_named_type(lowered_type, alias_name):
        return None
    return AliasDecl(
        name=alias_name,
        kind=AliasKind.TYPE_ALIAS,
        type_value=lowered_type,
        doc=doc,
    )


__all__ = [
    "is_named_type",
    "lower_typedef_alias",
]
