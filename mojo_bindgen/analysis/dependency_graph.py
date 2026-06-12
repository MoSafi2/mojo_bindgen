"""Declaration dependency graph for normalized CIR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.ir import (
    BinaryExpr,
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


@dataclass(frozen=True)
class DeclDependencyGraph:
    """Dependency edges from one top-level CIR declaration to other declarations."""

    edges_by_decl_id: dict[str, frozenset[str]]
    symbol_edges_by_decl_id: dict[str, frozenset[str]]


def build_decl_dependency_graph(unit: Unit) -> DeclDependencyGraph:
    """Build type/reference edges for declarations that have stable identities."""

    edges: dict[str, set[str]] = {}
    symbol_edges: dict[str, set[str]] = {}
    for decl in unit.decls:
        decl_id = _decl_id(decl)
        if decl_id is None:
            continue
        type_edges: set[str] = set()
        symbols: set[str] = set()
        for t in _decl_types(decl):
            _collect_type_edges(t, type_edges)
        for expr in _decl_exprs(decl):
            _collect_const_expr_edges(expr, type_edges, symbols)
        edges[decl_id] = type_edges
        symbol_edges[decl_id] = symbols

    return DeclDependencyGraph(
        edges_by_decl_id={decl_id: frozenset(values) for decl_id, values in edges.items()},
        symbol_edges_by_decl_id={
            decl_id: frozenset(values) for decl_id, values in symbol_edges.items()
        },
    )


def _decl_id(decl: Decl) -> str | None:
    if isinstance(decl, (Function, Struct, Typedef, GlobalVar)):
        return decl.decl_id
    if isinstance(decl, Enum):
        return decl.decl_id
    if isinstance(decl, (Const, MacroDecl)):
        return decl.name
    return None


def _decl_types(decl: Decl) -> tuple[Type, ...]:
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


def _decl_exprs(decl: Decl) -> tuple[ConstExpr, ...]:
    if isinstance(decl, Const):
        return (decl.expr,)
    if isinstance(decl, GlobalVar) and decl.initializer is not None:
        return (decl.initializer,)
    if isinstance(decl, MacroDecl) and decl.expr is not None:
        return (decl.expr,)
    return ()


def _collect_type_edges(t: Type, out: set[str]) -> None:
    for node in iter_type_nodes(
        t,
        options=TypeWalkOptions(descend_vector_element=True),
    ):
        if isinstance(node, (TypeRef, StructRef, EnumRef)):
            out.add(node.decl_id)


def _collect_const_expr_edges(
    expr: ConstExpr,
    type_edges: set[str],
    symbol_edges: set[str],
) -> None:
    if isinstance(expr, RefExpr):
        symbol_edges.add(expr.name)
        return
    if isinstance(expr, CastExpr):
        _collect_type_edges(expr.target, type_edges)
        _collect_const_expr_edges(expr.expr, type_edges, symbol_edges)
        return
    if isinstance(expr, SizeOfExpr):
        _collect_type_edges(expr.target, type_edges)
        return
    if isinstance(expr, UnaryExpr):
        _collect_const_expr_edges(expr.operand, type_edges, symbol_edges)
        return
    if isinstance(expr, BinaryExpr):
        _collect_const_expr_edges(expr.lhs, type_edges, symbol_edges)
        _collect_const_expr_edges(expr.rhs, type_edges, symbol_edges)


__all__ = [
    "DeclDependencyGraph",
    "build_decl_dependency_graph",
]
