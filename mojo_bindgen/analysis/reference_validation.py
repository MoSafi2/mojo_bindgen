"""Cross-declaration reference validation for normalized CIR."""

from __future__ import annotations

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.ir import (
    BinaryExpr,
    CastExpr,
    Const,
    ConstExpr,
    Enum,
    EnumRef,
    Function,
    GlobalVar,
    MacroDecl,
    OpaqueRecordRef,
    SizeOfExpr,
    Struct,
    StructRef,
    Type,
    Typedef,
    TypeRef,
    UnaryExpr,
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
            for t in _decl_types(decl):
                self._validate_type(
                    t,
                    struct_ids=struct_ids,
                    enum_ids=enum_ids,
                )
            for expr in _decl_exprs(decl):
                for t in _const_expr_types(expr):
                    self._validate_type(
                        t,
                        struct_ids=struct_ids,
                        enum_ids=enum_ids,
                    )
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


def _decl_types(decl) -> tuple[Type, ...]:
    if isinstance(decl, Function):
        return (decl.ret, *(param.type for param in decl.params))
    if isinstance(decl, Typedef):
        return (decl.aliased, decl.canonical)
    if isinstance(decl, Struct):
        return tuple(field.type for field in decl.fields)
    if isinstance(decl, GlobalVar):
        return (decl.type,)
    if isinstance(decl, Const):
        return (decl.type,)
    if isinstance(decl, MacroDecl):
        return () if decl.type is None else (decl.type,)
    return ()


def _decl_exprs(decl) -> tuple[ConstExpr, ...]:
    if isinstance(decl, Const):
        return (decl.expr,)
    if isinstance(decl, GlobalVar) and decl.initializer is not None:
        return (decl.initializer,)
    if isinstance(decl, MacroDecl) and decl.expr is not None:
        return (decl.expr,)
    return ()


def _const_expr_types(expr: ConstExpr) -> tuple[Type, ...]:
    out: list[Type] = []

    def walk(node: ConstExpr) -> None:
        if isinstance(node, CastExpr):
            out.append(node.target)
            walk(node.expr)
            return
        if isinstance(node, SizeOfExpr):
            out.append(node.target)
            return
        if isinstance(node, UnaryExpr):
            walk(node.operand)
            return
        if isinstance(node, BinaryExpr):
            walk(node.lhs)
            walk(node.rhs)

    walk(expr)
    return tuple(out)


__all__ = [
    "ReferenceValidationError",
    "ValidateReferencesPass",
]
