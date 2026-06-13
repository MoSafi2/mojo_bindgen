"""IR validation pass for structural pipeline invariants."""

from __future__ import annotations

from mojo_bindgen.analysis.traversal import iter_decl_referenced_types
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.ir import (
    Const,
    MacroDecl,
    OpaqueRecordRef,
    Struct,
    StructRef,
    Type,
    Typedef,
    TypeRef,
    Unit,
)


class IRValidationError(ValueError):
    """Raised when a Unit violates post-parse IR invariants."""


class ValidateIRPass:
    """Validate structural invariants required by downstream analysis.

    The pass is intentionally fail-fast and non-mutating. It guarantees stable
    declaration identities for declarations that participate in cross-reference
    analysis, and it verifies nested record/type references carry the identity
    fields needed by canonicalization, reachability, layout, and lowering. It
    does not prove ABI correctness or Mojo representability; later layout and
    lowering passes own those decisions.
    """

    def run(self, unit: Unit) -> Unit:
        decl_ids: dict[str, object] = {}
        struct_ids: set[str] = set()

        for decl in unit.decls:
            self._validate_decl_identity(decl, decl_ids)
            if isinstance(decl, Typedef):
                if not decl.decl_id:
                    raise IRValidationError(f"typedef {decl.name!r} is missing decl_id")
            elif isinstance(decl, Struct):
                if not decl.decl_id:
                    raise IRValidationError(f"struct {decl.name!r} is missing decl_id")
                struct_ids.add(decl.decl_id)

        for decl in unit.decls:
            for t in iter_decl_referenced_types(decl):
                self._validate_type(t, struct_ids)

        return unit

    def _validate_decl_identity(self, decl, decl_ids: dict[str, object]) -> None:
        if isinstance(decl, (Const, MacroDecl)):
            return
        decl_id = getattr(decl, "decl_id", None)
        if not decl_id:
            return
        prior = decl_ids.get(decl_id)
        if prior is not None and prior != decl:
            raise IRValidationError(f"duplicate decl_id {decl_id!r} in Unit")
        decl_ids[decl_id] = decl

    def _validate_type(self, t: Type, struct_ids: set[str]) -> None:
        for node in iter_type_nodes(t, options=TypeWalkOptions(descend_vector_element=True)):
            if isinstance(node, TypeRef) and not node.decl_id:
                raise IRValidationError(f"TypeRef {node.name!r} is missing decl_id")
            if isinstance(node, StructRef) and not node.decl_id:
                raise IRValidationError(f"StructRef {node.name!r} is missing decl_id")
            if isinstance(node, OpaqueRecordRef) and not node.decl_id:
                raise IRValidationError(f"OpaqueRecordRef {node.name!r} is missing decl_id")


__all__ = [
    "IRValidationError",
    "ValidateIRPass",
]
