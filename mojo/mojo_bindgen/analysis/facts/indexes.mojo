from ...ir import *


struct DeclIndexes(Copyable, Movable):
    var records_by_decl_id: Dict[String, Struct]
    var typedefs_by_decl_id: Dict[String, Typedef]
    var enums_by_decl_id: Dict[String, Enum]
    var functions_by_decl_id: Dict[String, Function]
    var globals_by_decl_id: Dict[String, GlobalVar]
    var consts_by_name: Dict[String, Const]
    var macros_by_name: Dict[String, MacroDecl]

    def __init__(out self):
        self.records_by_decl_id = Dict[String, Struct]()
        self.typedefs_by_decl_id = Dict[String, Typedef]()
        self.enums_by_decl_id = Dict[String, Enum]()
        self.functions_by_decl_id = Dict[String, Function]()
        self.globals_by_decl_id = Dict[String, GlobalVar]()
        self.consts_by_name = Dict[String, Const]()
        self.macros_by_name = Dict[String, MacroDecl]()


def build_decl_indexes(unit: Unit) -> DeclIndexes:
    var result = DeclIndexes()
    for decl in unit.decls:
        match decl:
            case .struct_decl(v):
                result.records_by_decl_id[v.decl_id] = v.copy()
            case .typedef(v):
                result.typedefs_by_decl_id[v.decl_id] = v.copy()
            case .enum_decl(v):
                result.enums_by_decl_id[v.decl_id] = v.copy()
            case .function(v):
                result.functions_by_decl_id[v.decl_id] = v.copy()
            case .global_var(v):
                result.globals_by_decl_id[v.decl_id] = v.copy()
            case .const_decl(v):
                result.consts_by_name[v.name] = v.copy()
            case .macro_decl(v):
                result.macros_by_name[v.name] = v.copy()
    return result^


def record_by_decl_id(unit: Unit) -> Dict[String, Struct]:
    return build_decl_indexes(unit).records_by_decl_id.copy()


def struct_by_decl_id(unit: Unit) -> Dict[String, Struct]:
    var result = Dict[String, Struct]()
    for decl in unit.decls:
        match decl:
            case .struct_decl(v):
                if not v.is_union:
                    result[v.decl_id] = v.copy()
            case _:
                pass
    return result^
