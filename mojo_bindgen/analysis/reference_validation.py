"""Cross-declaration reference validation for normalized CIR."""

from __future__ import annotations

from mojo_bindgen.analysis.traversal import iter_decl_referenced_types
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.ir import (
    Enum,
    EnumRef,
    OpaqueRecordRef,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Unit,
)


class ReferenceValidationError(ValueError):
    """Raised when normalized CIR contains an invalid internal reference."""


class ValidateReferencesPass:
    """Validate cross-declaration references that must resolve inside the ``Unit``.

    Missing ``TypeRef`` declarations are treated as external typedef uses because
    ``LowerUnitPass`` can synthesize aliases for those. ``OpaqueRecordRef`` is
    also allowed to remain external. Concrete non-union ``StructRef`` and all
    ``EnumRef`` nodes must resolve after signature-stub materialization and enum
    canonicalization.
    """

    def run(self, unit: Unit) -> Unit:
        struct_ids = {decl.decl_id for decl in unit.decls if isinstance(decl, Struct)}
        enum_ids = {decl.decl_id for decl in unit.decls if isinstance(decl, Enum)}

        for decl in unit.decls:
            for t in iter_decl_referenced_types(decl):
                self._validate_type(t, struct_ids=struct_ids, enum_ids=enum_ids)
        return unit

    def _validate_type(
        self,
        t: Type,
        *,
        struct_ids: set[str],
        enum_ids: set[str],
    ) -> None:
        for node in iter_type_nodes(
            t,
            options=TypeWalkOptions(descend_vector_element=True),
        ):
            if isinstance(node, TypeRef):
                if not node.decl_id:
                    raise ReferenceValidationError(f"TypeRef {node.name!r} is missing decl_id")
                # External typedef refs are supported by synthetic alias lowering.
                continue
            if isinstance(node, StructRef):
                if node.decl_id not in struct_ids and not node.is_union:
                    raise ReferenceValidationError(
                        f"StructRef {node.name!r} points to missing decl_id {node.decl_id!r}"
                    )
                continue
            if isinstance(node, EnumRef) and node.decl_id not in enum_ids:
                raise ReferenceValidationError(
                    f"EnumRef {node.name!r} points to missing decl_id {node.decl_id!r}"
                )
            if isinstance(node, OpaqueRecordRef):
                continue


__all__ = [
    "ReferenceValidationError",
    "ValidateReferencesPass",
]
