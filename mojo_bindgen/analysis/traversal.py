"""Shared traversal helpers for normalized CIR declarations and expressions."""

from __future__ import annotations

from collections.abc import Iterator

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.ir import (
    BinaryExpr,
    CallExpr,
    CastExpr,
    Const,
    ConstExpr,
    Decl,
    Enum,
    EnumRef,
    Function,
    GlobalVar,
    MacroDecl,
    RefExpr,
    SizeOfExpr,
    Struct,
    StructRef,
    Type,
    Typedef,
    TypeRef,
    UnaryExpr,
    Unit,
)


def decl_id(decl: Decl) -> str | None:
    """Return the stable dependency-graph id for declarations that have one."""

    if isinstance(decl, (Function, Struct, Enum, Typedef, GlobalVar)):
        return decl.decl_id
    if isinstance(decl, (Const, MacroDecl)):
        return decl.name
    return None


def iter_decl_types(decl: Decl) -> Iterator[Type]:
    """Yield direct type slots owned by one top-level declaration."""

    if isinstance(decl, Function):
        yield decl.ret
        for param in decl.params:
            yield param.type
        return
    if isinstance(decl, Typedef):
        yield decl.aliased
        yield decl.canonical
        return
    if isinstance(decl, Struct):
        for field in decl.fields:
            yield field.type
        return
    if isinstance(decl, GlobalVar):
        yield decl.type
        return
    if isinstance(decl, Const):
        yield decl.type
        return
    if isinstance(decl, MacroDecl) and decl.type is not None:
        yield decl.type


def iter_decl_const_exprs(decl: Decl) -> Iterator[ConstExpr]:
    """Yield direct constant-expression slots owned by one declaration."""

    if isinstance(decl, Const):
        yield decl.expr
        return
    if isinstance(decl, GlobalVar) and decl.initializer is not None:
        yield decl.initializer
        return
    if isinstance(decl, MacroDecl) and decl.expr is not None:
        yield decl.expr


def iter_const_expr_nodes(expr: ConstExpr) -> Iterator[ConstExpr]:
    """Yield a constant expression and descendants in preorder."""

    yield expr
    if isinstance(expr, CastExpr):
        yield from iter_const_expr_nodes(expr.expr)
        return
    if isinstance(expr, UnaryExpr):
        yield from iter_const_expr_nodes(expr.operand)
        return
    if isinstance(expr, BinaryExpr):
        yield from iter_const_expr_nodes(expr.lhs)
        yield from iter_const_expr_nodes(expr.rhs)
        return
    if isinstance(expr, CallExpr):
        yield from iter_const_expr_nodes(expr.callee)
        for arg in expr.args:
            yield from iter_const_expr_nodes(arg)


def iter_const_expr_types(expr: ConstExpr) -> Iterator[Type]:
    """Yield type slots referenced by a constant-expression tree."""

    for node in iter_const_expr_nodes(expr):
        if isinstance(node, CastExpr):
            yield node.target
        elif isinstance(node, SizeOfExpr):
            yield node.target


def iter_const_expr_refs(expr: ConstExpr) -> Iterator[RefExpr]:
    """Yield symbol references from a constant-expression tree."""

    for node in iter_const_expr_nodes(expr):
        if isinstance(node, RefExpr):
            yield node


def iter_decl_referenced_types(decl: Decl) -> Iterator[Type]:
    """Yield declaration type slots plus type slots nested in const expressions."""

    yield from iter_decl_types(decl)
    for expr in iter_decl_const_exprs(decl):
        yield from iter_const_expr_types(expr)


def iter_unit_typerefs(unit: Unit) -> Iterator[TypeRef]:
    """Yield all ``TypeRef`` nodes used by declarations and const expressions."""

    for decl in unit.decls:
        for t in iter_decl_referenced_types(decl):
            for node in iter_type_nodes(
                t,
                options=TypeWalkOptions(descend_vector_element=True),
            ):
                if isinstance(node, TypeRef):
                    yield node


def iter_type_decl_refs(
    t: Type,
    *,
    options: TypeWalkOptions | None = None,
) -> Iterator[TypeRef | StructRef | EnumRef]:
    """Yield declaration-reference type nodes inside one type tree."""

    for node in iter_type_nodes(t, options=options):
        if isinstance(node, (TypeRef, StructRef, EnumRef)):
            yield node


__all__ = [
    "decl_id",
    "iter_const_expr_nodes",
    "iter_const_expr_refs",
    "iter_const_expr_types",
    "iter_decl_const_exprs",
    "iter_decl_referenced_types",
    "iter_decl_types",
    "iter_type_decl_refs",
    "iter_unit_typerefs",
]
