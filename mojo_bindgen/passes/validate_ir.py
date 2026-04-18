"""IR validation pass for structural pipeline invariants."""

from __future__ import annotations

from mojo_bindgen.ir import (
    Array,
    AtomicType,
    Function,
    FunctionPtr,
    GlobalVar,
    OpaqueRecordRef,
    Param,
    Pointer,
    QualifiedType,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    Unit,
)


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
        if isinstance(t, TypeRef):
            if not t.decl_id:
                raise IRValidationError(f"TypeRef {t.name!r} is missing decl_id")
            self._validate_type(t.canonical, struct_ids)
            return
        if isinstance(t, StructRef):
            if not t.decl_id:
                raise IRValidationError(f"StructRef {t.name!r} is missing decl_id")
            return
        if isinstance(t, OpaqueRecordRef):
            if not t.decl_id:
                raise IRValidationError(f"OpaqueRecordRef {t.name!r} is missing decl_id")
            return
        if isinstance(t, QualifiedType):
            self._validate_type(t.unqualified, struct_ids)
            return
        if isinstance(t, AtomicType):
            self._validate_type(t.value_type, struct_ids)
            return
        if isinstance(t, Pointer):
            if t.pointee is not None:
                self._validate_type(t.pointee, struct_ids)
            return
        if isinstance(t, Array):
            self._validate_type(t.element, struct_ids)
            return
        if isinstance(t, FunctionPtr):
            self._validate_type(t.ret, struct_ids)
            for param in t.params:
                self._validate_type(param, struct_ids)
