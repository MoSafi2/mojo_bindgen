from ...ir import *
from ..traversal import iter_decl_referenced_types
from ..type_walk import iter_type_nodes, TypeWalkOptions
from ..mojo.type_mapping import exact_width_stdint_alias_type


__enum AliasClass(Equatable, ImplicitlyCopyable, Movable):
    case CALLBACK
    case ENUM
    case EXACT_WIDTH_STDINT
    case EXTERNAL_TYPEDEF
    case NO_OP_SELF_ALIAS
    case RECORD
    case TYPEDEF

    def value(self) -> String:
        match self:
            case .CALLBACK:
                return "callback"
            case .ENUM:
                return "enum"
            case .EXACT_WIDTH_STDINT:
                return "exact_width_stdint"
            case .EXTERNAL_TYPEDEF:
                return "external_typedef"
            case .NO_OP_SELF_ALIAS:
                return "no_op_self_alias"
            case .RECORD:
                return "record"
            case .TYPEDEF:
                return "typedef"


@fieldwise_init
struct AliasInfo(Copyable, Movable):
    var decl_id: String
    var name: String
    var alias_class: AliasClass
    var target_decl_id: Optional[String]


@fieldwise_init
struct AliasClassification(Copyable, Movable):
    var aliases_by_decl_id: Dict[String, AliasInfo]
    var external_aliases_by_decl_id: Dict[String, AliasInfo]
    var external_type_refs_by_decl_id: Dict[String, TypeRef]


def _target(t: CType) -> Optional[CType]:
    match t:
        case .type_ref(v):
            return _target(v.canonical.ptr()[])
        case .enum_ref(_) | .struct_ref(_):
            return t.copy()
        case _:
            return {}


def _target_id(t: CType) -> Optional[String]:
    var v = _target(t)
    if v:
        match v.value():
            case .enum_ref(e):
                return e.decl_id.copy()
            case .struct_ref(e):
                return e.decl_id.copy()
            case _:
                pass
    return {}


def classify_aliases(unit: Unit) -> AliasClassification:
    var local = Dict[String, Bool]()
    var aliases = Dict[String, AliasInfo]()
    var external = Dict[String, AliasInfo]()
    var refs = Dict[String, TypeRef]()
    for decl in unit.decls:
        match decl:
            case .typedef(v):
                local[v.decl_id] = True
                var category = AliasClass.TYPEDEF
                var target = _target(v.aliased.ptr()[])
                if not target:
                    target = _target(v.canonical.ptr()[])
                if exact_width_stdint_alias_type(v.name):
                    category = AliasClass.EXACT_WIDTH_STDINT
                else:
                    var callback = False
                    match v.aliased.ptr()[]:
                        case .c_function_ptr(_):
                            callback = True
                        case _:
                            pass
                    match v.canonical.ptr()[]:
                        case .c_function_ptr(_):
                            callback = True
                        case _:
                            pass
                    if callback:
                        category = AliasClass.CALLBACK
                    elif target:
                        match target.value():
                            case .enum_ref(_):
                                category = AliasClass.ENUM
                            case .struct_ref(_):
                                category = AliasClass.RECORD
                            case _:
                                pass
                    else:
                        match v.aliased.ptr()[]:
                            case .type_ref(r):
                                if r.decl_id == v.decl_id:
                                    category = AliasClass.NO_OP_SELF_ALIAS
                            case _:
                                pass
                var key = _target_id(v.aliased.ptr()[])
                if not key:
                    key = _target_id(v.canonical.ptr()[])
                aliases[v.decl_id] = AliasInfo(v.decl_id.copy(), v.name.copy(), category, key^)
            case _:
                pass
    for decl in unit.decls:
        for t in iter_decl_referenced_types(decl):
            for node in iter_type_nodes(t.ptr()[], TypeWalkOptions(descend_vector_element=True)):
                match node.ptr()[]:
                    case .type_ref(v):
                        if v.decl_id in local or v.decl_id in external:
                            continue
                        external[v.decl_id] = AliasInfo(
                            v.decl_id.copy(),
                            v.name.copy(),
                            AliasClass.EXTERNAL_TYPEDEF,
                            _target_id(v.canonical.ptr()[]),
                        )
                        refs[v.decl_id] = v.copy()
                    case _:
                        pass
    return AliasClassification(aliases^, external^, refs^)
