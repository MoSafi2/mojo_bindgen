from ...ir import *
from ..traversal import iter_decl_referenced_types
from ..type_walk import iter_type_nodes, TypeWalkOptions
from ..common import quoted


struct ValidateReferencesPass:
    def __init__(out self):
        pass

    def run(self, unit: Unit) raises -> Unit:
        var structs = Dict[String, Bool]()
        var enums = Dict[String, Bool]()
        for decl in unit.decls:
            match decl:
                case .struct_decl(v):
                    structs[v.decl_id] = True
                case .enum_decl(v):
                    enums[v.decl_id] = True
                case _:
                    pass
        for decl in unit.decls:
            for t in iter_decl_referenced_types(decl):
                for node in iter_type_nodes(
                    t.ptr()[], TypeWalkOptions(descend_vector_element=True)
                ):
                    match node.ptr()[]:
                        case .type_ref(v):
                            if not v.decl_id.byte_length():
                                raise Error("TypeRef " + quoted(v.name) + " is missing decl_id")
                        case .struct_ref(v):
                            if v.decl_id not in structs and not v.is_union:
                                raise Error(
                                    "StructRef "
                                    + quoted(v.name)
                                    + " points to missing decl_id "
                                    + quoted(v.decl_id)
                                )
                        case .enum_ref(v):
                            if v.decl_id not in enums:
                                raise Error(
                                    "EnumRef "
                                    + quoted(v.name)
                                    + " points to missing decl_id "
                                    + quoted(v.decl_id)
                                )
                        case _:
                            pass
        return unit.copy()
