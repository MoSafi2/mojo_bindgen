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
        typedef_ids: set[str] = set()
        struct_ids: set[str] = set()

        for decl in unit.decls:
            decl_id = getattr(decl, "decl_id", None)
            if decl_id:
                prior = decl_ids.get(decl_id)
                if prior is not None:
                    raise IRValidationError(f"duplicate decl_id {decl_id!r} in Unit")
                decl_ids[decl_id] = decl
            if isinstance(decl, Typedef):
                if not decl.decl_id:
                    raise IRValidationError(f"typedef {decl.name!r} is missing decl_id")
                typedef_ids.add(decl.decl_id)
            elif isinstance(decl, Struct):
                if not decl.decl_id:
                    raise IRValidationError(f"struct {decl.name!r} is missing decl_id")
                struct_ids.add(decl.decl_id)

        for decl in unit.decls:
            if isinstance(decl, Struct):
                for field in decl.fields:
                    self._validate_type(field.type, typedef_ids, struct_ids)
            elif isinstance(decl, Typedef):
                self._validate_type(decl.aliased, typedef_ids, struct_ids)
                self._validate_type(decl.canonical, typedef_ids, struct_ids)
            elif isinstance(decl, Function):
                self._validate_type(decl.ret, typedef_ids, struct_ids)
                for param in decl.params:
                    self._validate_param(param, typedef_ids, struct_ids)
            elif isinstance(decl, GlobalVar):
                self._validate_type(decl.type, typedef_ids, struct_ids)

        return unit

    def _validate_param(self, param: Param, typedef_ids: set[str], struct_ids: set[str]) -> None:
        self._validate_type(param.type, typedef_ids, struct_ids)

    def _validate_type(self, t: Type, typedef_ids: set[str], struct_ids: set[str]) -> None:
        if isinstance(t, TypeRef):
            if not t.decl_id:
                raise IRValidationError(f"TypeRef {t.name!r} is missing decl_id")
            if t.decl_id not in typedef_ids:
                raise IRValidationError(f"TypeRef {t.name!r} points to unknown typedef decl_id {t.decl_id!r}")
            self._validate_type(t.canonical, typedef_ids, struct_ids)
            return
        if isinstance(t, StructRef):
            if not t.decl_id:
                raise IRValidationError(f"StructRef {t.name!r} is missing decl_id")
            if t.decl_id not in struct_ids:
                raise IRValidationError(f"StructRef {t.name!r} points to unknown struct decl_id {t.decl_id!r}")
            return
        if isinstance(t, OpaqueRecordRef):
            if not t.decl_id:
                raise IRValidationError(f"OpaqueRecordRef {t.name!r} is missing decl_id")
            return
        if isinstance(t, QualifiedType):
            self._validate_type(t.unqualified, typedef_ids, struct_ids)
            return
        if isinstance(t, AtomicType):
            self._validate_type(t.value_type, typedef_ids, struct_ids)
            return
        if isinstance(t, Pointer):
            if t.pointee is not None:
                self._validate_type(t.pointee, typedef_ids, struct_ids)
            return
        if isinstance(t, Array):
            self._validate_type(t.element, typedef_ids, struct_ids)
            return
        if isinstance(t, FunctionPtr):
            self._validate_type(t.ret, typedef_ids, struct_ids)
            for param in t.params:
                self._validate_type(param, typedef_ids, struct_ids)
