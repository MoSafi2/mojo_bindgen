"""Fail-fast source invariants, with independent owning-cycle validation."""
from ...ir import *
from ..traversal import (
    decl_id,
    iter_decl_referenced_types,
    iter_decl_const_exprs,
    validate_expression,
)
from ..type_walk import validate_type_tree, iter_type_nodes, TypeWalkOptions
from ..common import quoted


struct ValidateIRPass:
    def __init__(out self):
        pass

    def run(self, unit: Unit) raises -> Unit:
        var ids = Dict[String, Decl]()
        for decl in unit.decls:
            var key = decl_id(decl)
            if key:
                if key.value() in ids and not equal(decl, ids[key.value()]):
                    raise Error("duplicate decl_id " + quoted(key.value()) + " in Unit")
                ids[key.value()] = decl.copy()
            match decl:
                case .struct_decl(v):
                    if not v.decl_id.byte_length():
                        raise Error("struct " + quoted(v.name) + " is missing decl_id")
                case .typedef(v):
                    if not v.decl_id.byte_length():
                        raise Error("typedef " + quoted(v.name) + " is missing decl_id")
                case _:
                    pass
        for decl in unit.decls:
            for expr in iter_decl_const_exprs(decl):
                validate_expression(expr.ptr()[])
            for t in iter_decl_referenced_types(decl):
                validate_type_tree(t.ptr()[])
                for node in iter_type_nodes(
                    t.ptr()[], TypeWalkOptions(descend_vector_element=True)
                ):
                    var name: String
                    var key: String
                    var tag: String
                    match node.ptr()[]:
                        case .type_ref(v):
                            name = v.name.copy()
                            key = v.decl_id.copy()
                            tag = "TypeRef"
                        case .struct_ref(v):
                            name = v.name.copy()
                            key = v.decl_id.copy()
                            tag = "StructRef"
                        case .opaque_record_ref(v):
                            name = v.name.copy()
                            key = v.decl_id.copy()
                            tag = "OpaqueRecordRef"
                        case _:
                            continue
                    if not key.byte_length():
                        raise Error(tag + " " + quoted(name) + " is missing decl_id")
        return unit.copy()
