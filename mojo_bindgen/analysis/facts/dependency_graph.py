"""Declaration dependency graph for normalized CIR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.traversal import (
    decl_id,
    iter_const_expr_refs,
    iter_const_expr_types,
    iter_decl_const_exprs,
    iter_decl_types,
    iter_type_decl_refs,
)
from mojo_bindgen.analysis.type_walk import TypeWalkOptions
from mojo_bindgen.ir import Type, Unit


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
        current_id = decl_id(decl)
        if current_id is None:
            continue
        type_edges: set[str] = set()
        symbols: set[str] = set()
        for t in iter_decl_types(decl):
            _collect_type_edges(t, type_edges)
        for expr in iter_decl_const_exprs(decl):
            for t in iter_const_expr_types(expr):
                _collect_type_edges(t, type_edges)
            symbols.update(ref.name for ref in iter_const_expr_refs(expr))
        edges[current_id] = type_edges
        symbol_edges[current_id] = symbols

    return DeclDependencyGraph(
        edges_by_decl_id={decl_id: frozenset(values) for decl_id, values in edges.items()},
        symbol_edges_by_decl_id={
            decl_id: frozenset(values) for decl_id, values in symbol_edges.items()
        },
    )


def _collect_type_edges(t: Type, out: set[str]) -> None:
    for node in iter_type_decl_refs(
        t,
        options=TypeWalkOptions(descend_vector_element=True),
    ):
        out.add(node.decl_id)


__all__ = [
    "DeclDependencyGraph",
    "build_decl_dependency_graph",
]
