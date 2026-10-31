from ...ir import *
from ..traversal import (
    decl_id,
    iter_decl_types,
    iter_decl_const_exprs,
    iter_const_expr_types,
    iter_const_expr_refs,
    referenced_id,
)
from ..type_walk import iter_type_nodes, TypeWalkOptions


@fieldwise_init
struct DeclDependencyGraph(Copyable, Movable):
    var edges_by_decl_id: Dict[String, Dict[String, Bool]]
    var symbol_edges_by_decl_id: Dict[String, Dict[String, Bool]]


def build_decl_dependency_graph(unit: Unit) -> DeclDependencyGraph:
    var edges = Dict[String, Dict[String, Bool]]()
    var symbols = Dict[String, Dict[String, Bool]]()
    for decl in unit.decls:
        var key = decl_id(decl)
        if not key:
            continue
        var types = iter_decl_types(decl)
        var refs = Dict[String, Bool]()
        for expr in iter_decl_const_exprs(decl):
            types.extend(iter_const_expr_types(expr.ptr()[]))
            for name in iter_const_expr_refs(expr.ptr()[]):
                refs[name] = True
        var dependencies = Dict[String, Bool]()
        for t in types:
            for node in iter_type_nodes(t.ptr()[], TypeWalkOptions(descend_vector_element=True)):
                var target = referenced_id(node.ptr()[])
                if target:
                    dependencies[target.value()] = True
        edges[key.value()] = dependencies^
        symbols[key.value()] = refs^
    return DeclDependencyGraph(edges^, symbols^)
