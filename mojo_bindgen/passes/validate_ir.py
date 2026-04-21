"""IR validation pass for structural pipeline invariants."""

from __future__ import annotations

from mojo_bindgen.ir import Function, GlobalVar, OpaqueRecordRef, Param, Struct, StructRef, Type, TypeRef, Typedef, Unit
from mojo_bindgen.passes.semantic.type_walk import iter_type_nodes


class IRValidationError(ValueError):
    """Raised when a Unit violates post-parse IR invariants."""


class ValidateIRPass:
    """Validate basic declaration identity and type-reference invariants."""

    def run(self, unit: Unit) -> Unit:
        decl_ids: dict[str, object] = {}
        struct_ids: set[str] = set()

        for decl in unit.decls:
            decl_id = getattr(decl, "decl_id", None)
            if decl_id:
                prior = decl_ids.get(decl_id)
                if prior is not None and prior != decl:
                    raise IRValidationError(f"duplicate decl_id {decl_id!r} in Unit")
                decl_ids[decl_id] = decl
            if isinstance(decl, Typedef):
                if not decl.decl_id:
                    raise IRValidationError(f"typedef {decl.name!r} is missing decl_id")
            elif isinstance(decl, Struct):
                if not decl.decl_id:
                    raise IRValidationError(f"struct {decl.name!r} is missing decl_id")
                struct_ids.add(decl.decl_id)

        for decl in unit.decls:
            if isinstance(decl, Struct):
                for field in decl.fields:
                    self._validate_type(field.type, struct_ids)
            elif isinstance(decl, Typedef):
                self._validate_type(decl.aliased, struct_ids)
                self._validate_type(decl.canonical, struct_ids)
            elif isinstance(decl, Function):
                self._validate_type(decl.ret, struct_ids)
                for param in decl.params:
                    self._validate_param(param, struct_ids)
            elif isinstance(decl, GlobalVar):
                self._validate_type(decl.type, struct_ids)

        return unit

    def _validate_param(self, param: Param, struct_ids: set[str]) -> None:
        self._validate_type(param.type, struct_ids)

    def _validate_type(self, t: Type, struct_ids: set[str]) -> None:
        for node in iter_type_nodes(t):
            if isinstance(node, TypeRef) and not node.decl_id:
                raise IRValidationError(f"TypeRef {node.name!r} is missing decl_id")
            if isinstance(node, StructRef) and not node.decl_id:
                raise IRValidationError(f"StructRef {node.name!r} is missing decl_id")
            if isinstance(node, OpaqueRecordRef) and not node.decl_id:
                raise IRValidationError(f"OpaqueRecordRef {node.name!r} is missing decl_id")
