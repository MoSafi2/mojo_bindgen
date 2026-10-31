from ..common import sort_strings
from ...ir import *
from ..traversal import iter_decl_types, iter_decl_const_exprs, iter_const_expr_types
from ..type_walk import iter_type_nodes, TypeWalkOptions


struct SignatureRecordStubOptions(Copyable, Movable):
    var traverse_function_ptrs: Bool
    var traverse_const_expr_types: Bool
    var synthesize_union_refs: Bool

    def __init__(
        out self,
        traverse_function_ptrs: Bool = True,
        traverse_const_expr_types: Bool = True,
        synthesize_union_refs: Bool = False,
    ):
        self.traverse_function_ptrs = traverse_function_ptrs
        self.traverse_const_expr_types = traverse_const_expr_types
        self.synthesize_union_refs = synthesize_union_refs


@fieldwise_init
struct SignatureRecordStubResult(Copyable, Movable):
    var unit: Unit
    var synthesized_structs: List[Struct]
    var reachable_orphan_decl_ids: List[String]


struct SignatureRecordStubPass:
    def __init__(out self):
        pass

    def run(
        self, unit: Unit, options: SignatureRecordStubOptions = SignatureRecordStubOptions()
    ) raises -> SignatureRecordStubResult:
        var existing = Dict[String, Bool]()
        for decl in unit.decls:
            match decl:
                case .struct_decl(v):
                    existing[v.decl_id] = True
                case _:
                    pass
        var refs = Dict[String, StructRef]()
        var ids = List[String]()
        for decl in unit.decls:
            var types = iter_decl_types(decl)
            if options.traverse_const_expr_types:
                for expr in iter_decl_const_exprs(decl):
                    types.extend(iter_const_expr_types(expr.ptr()[]))
            for t in types:
                for node in iter_type_nodes(
                    t.ptr()[],
                    TypeWalkOptions(
                        descend_function_ptr=options.traverse_function_ptrs,
                        descend_vector_element=True,
                    ),
                ):
                    match node.ptr()[]:
                        case .struct_ref(v):
                            if (
                                v.decl_id in existing
                                or v.decl_id in refs
                                or (v.is_union and not options.synthesize_union_refs)
                            ):
                                continue
                            refs[v.decl_id] = v.copy()
                            ids.append(v.decl_id.copy())
                        case _:
                            pass
        sort_strings(ids)
        var added = List[Struct]()
        var output = unit.copy()
        output.decls = List[Decl]()
        for key in ids:
            var v = refs[key].copy()
            var record = Struct(
                v.decl_id.copy(),
                v.name.copy(),
                v.c_name.copy(),
                List[Field](),
                0,
                1,
                is_union=v.is_union,
                is_anonymous=v.is_anonymous,
                is_complete=False,
            )
            added.append(record.copy())
            output.decls.append(Decl.struct_decl(record^))
        output.decls.extend(unit.decls.copy())
        return SignatureRecordStubResult(output^, added^, ids^)
