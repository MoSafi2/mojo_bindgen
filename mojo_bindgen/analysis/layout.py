"""Backend-neutral layout and struct-index helpers."""

from __future__ import annotations

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, any_type_node
from mojo_bindgen.codegen.mojo_mapper import map_atomic_type
from mojo_bindgen.ir import (
    AtomicType,
    Field,
    Struct,
    Unit,
)


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map struct ``decl_id`` to :class:`Struct`, including incomplete non-unions."""
    out: dict[str, Struct] = {}
    for decl in unit.decls:
        if isinstance(decl, Struct) and not decl.is_union:
            out[decl.decl_id] = decl
    return out


_EMBEDDED_ATOMIC_WALK = TypeWalkOptions(
    peel_typeref=True,
    peel_qualified=True,
    peel_atomic=False,
    descend_pointer=False,
    descend_array=True,
    descend_function_ptr=False,
    descend_vector_element=False,
)


def field_contains_representable_atomic_storage(field: Field) -> bool:
    return any_type_node(
        field.type,
        lambda node: isinstance(node, AtomicType) and map_atomic_type(node) is not None,
        options=_EMBEDDED_ATOMIC_WALK,
    )
