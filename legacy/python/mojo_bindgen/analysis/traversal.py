"""Shared traversal helpers for normalized CIR declarations and expressions."""

from __future__ import annotations

from collections.abc import Iterator
from typing import assert_never

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.ir import (
    CBinaryExpr,
    CCallExpr,
    CCastExpr,
    CConstExpr,
    CFloatLiteral,
    CharLiteral,
    CNullPtrLiteral,
    Const,
    CRefExpr,
    CSizeOfExpr,
    CType,
    CUnaryExpr,
    Decl,
    Enum,
    EnumRef,
    Function,
    GlobalVar,
    IntLiteral,
    MacroDecl,
    StringLiteral,
    Struct,
    StructRef,
    Typedef,
    TypeRef,
    Unit,
)


def decl_id(decl: Decl) -> str | None:
    """Return the stable dependency-graph id for declarations that have one."""

    if isinstance(decl, (Function, Struct, Enum, Typedef, GlobalVar)):
        return decl.decl_id
    if isinstance(decl, (Const, MacroDecl)):
        return decl.name
    assert_never(decl)


def iter_decl_types(decl: Decl) -> Iterator[CType]:
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
    if isinstance(decl, MacroDecl):
        if decl.type is not None:
            yield decl.type
        return
    if isinstance(decl, Enum):
        yield decl.underlying
        return
    assert_never(decl)


def iter_decl_const_exprs(decl: Decl) -> Iterator[CConstExpr]:
    """Yield direct constant-expression slots owned by one declaration."""

    if isinstance(decl, Const):
        yield decl.expr
        return
    if isinstance(decl, GlobalVar):
        if decl.initializer is not None:
            yield decl.initializer
        return
    if isinstance(decl, MacroDecl):
        if decl.expr is not None:
            yield decl.expr
        return
    if isinstance(decl, (Function, Struct, Enum, Typedef)):
        return
    assert_never(decl)


def iter_const_expr_nodes(expr: CConstExpr) -> Iterator[CConstExpr]:
    """Yield a constant expression and descendants in preorder."""

    yield expr
    if isinstance(expr, CCastExpr):
        yield from iter_const_expr_nodes(expr.expr)
        return
    if isinstance(expr, CUnaryExpr):
        yield from iter_const_expr_nodes(expr.operand)
        return
    if isinstance(expr, CBinaryExpr):
        yield from iter_const_expr_nodes(expr.lhs)
        yield from iter_const_expr_nodes(expr.rhs)
        return
    if isinstance(expr, CCallExpr):
        yield from iter_const_expr_nodes(expr.callee)
        for arg in expr.args:
            yield from iter_const_expr_nodes(arg)
        return
    if isinstance(
        expr,
        (
            IntLiteral,
            CFloatLiteral,
            StringLiteral,
            CharLiteral,
            CNullPtrLiteral,
            CRefExpr,
            CSizeOfExpr,
        ),
    ):
        return
    assert_never(expr)


def iter_const_expr_types(expr: CConstExpr) -> Iterator[CType]:
    """Yield type slots referenced by a constant-expression tree."""

    for node in iter_const_expr_nodes(expr):
        if isinstance(node, CCastExpr):
            yield node.target
        elif isinstance(node, CSizeOfExpr):
            yield node.target


def iter_const_expr_refs(expr: CConstExpr) -> Iterator[CRefExpr]:
    """Yield symbol references from a constant-expression tree."""

    for node in iter_const_expr_nodes(expr):
        if isinstance(node, CRefExpr):
            yield node


def iter_decl_referenced_types(decl: Decl) -> Iterator[CType]:
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
    t: CType,
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
