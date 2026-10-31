from ...ir import *
from ..common import mojo_ident
from ._rewrite import EnumResolution, rewrite_decl


def _enum_ref(t: CType) raises -> Optional[EnumRef]:
    match t:
        case .enum_ref(v):
            return v.copy()
        case .type_ref(v):
            return _enum_ref(v.canonical.ptr()[])
        case _:
            return {}


def _same_function(a: Function, b: Function) raises -> Bool:
    if (
        a.name != b.name
        or a.link_name != b.link_name
        or not equal(a.ret, b.ret)
        or a.is_variadic != b.is_variadic
        or not equal(a.calling_convention, b.calling_convention)
        or not equal(a.attrs, b.attrs)
        or len(a.params) != len(b.params)
    ):
        return False
    for i in range(len(a.params)):
        if not equal(a.params[i].type, b.params[i].type):
            return False
    return True


struct CIRCanonicalizer:
    def __init__(out self):
        pass

    def canonicalize(self, unit: Unit) raises -> Unit:
        var records = Dict[String, Struct]()
        var decls = List[Decl]()
        for d in unit.decls:
            match d:
                case .struct_decl(v):
                    if v.decl_id not in records or (
                        v.is_complete and not records[v.decl_id].is_complete
                    ):
                        records[v.decl_id] = v.copy()
                case _:
                    decls.append(d.copy())
        for v in records.values():
            decls.append(Decl.struct_decl(v.copy()))
        var functions = List[Function]()
        var filtered = List[Decl]()
        for d in decls:
            var duplicate = False
            match d:
                case .function(v):
                    for previous in functions:
                        if _same_function(v, previous):
                            duplicate = True
                            break
                    if not duplicate:
                        functions.append(v.copy())
                case _:
                    pass
            if not duplicate:
                filtered.append(d.copy())
        var last = Dict[String, Int]()
        var claimed = Dict[String, Bool]()
        for i in range(len(filtered)):
            match filtered[i]:
                case .macro_decl(v):
                    last[v.name] = i
                case .const_decl(v):
                    claimed[v.name] = True
                case .enum_decl(v):
                    for e in v.enumerants:
                        claimed[e.name] = True
                case _:
                    pass
        decls = List[Decl]()
        for i in range(len(filtered)):
            match filtered[i]:
                case .macro_decl(v):
                    if last[v.name] != i:
                        continue
                    if v.expr:
                        match v.expr.value().ptr()[]:
                            case .c_ref_expr(e):
                                if e.name == v.name and v.name in claimed:
                                    continue
                            case _:
                                pass
                case _:
                    pass
            decls.append(filtered[i].copy())
        var typedefs = Dict[String, List[String]]()
        var ordinary = Dict[String, Bool]()
        var enums = Dict[String, Enum]()
        for d in decls:
            match d:
                case .enum_decl(v):
                    enums[v.decl_id] = v.copy()
                    for e in v.enumerants:
                        ordinary[mojo_ident(e.name)] = True
                case .typedef(v):
                    ordinary[mojo_ident(v.name)] = True
                    var target = _enum_ref(v.aliased.ptr()[])
                    if not target:
                        target = _enum_ref(v.canonical.ptr()[])
                    if target:
                        var key = target.value().decl_id.copy()
                        if key not in typedefs:
                            typedefs[key] = List[String]()
                        typedefs[key].append(v.name.copy())
                case .struct_decl(v):
                    ordinary[mojo_ident(v.name)] = True
                case .function(v):
                    ordinary[mojo_ident(v.name)] = True
                case .global_var(v):
                    ordinary[mojo_ident(v.name)] = True
                case .const_decl(v):
                    ordinary[mojo_ident(v.name)] = True
                case .macro_decl(v):
                    ordinary[mojo_ident(v.name)] = True
        var names = Dict[String, EnumResolution]()
        var claimed_enums = Dict[String, Bool]()
        for d in decls:
            match d:
                case .enum_decl(v):
                    var e = enums[v.decl_id].copy()
                    var tag = String()
                    if not e.is_anonymous:
                        tag = e.c_name.copy()
                    var primary = e.name.copy()
                    if tag.byte_length():
                        primary = tag.copy()
                    if v.decl_id in typedefs and len(typedefs[v.decl_id]):
                        primary = typedefs[v.decl_id][0].copy()
                    var aliases = List[String]()
                    var p = mojo_ident(primary)
                    var t = mojo_ident(tag)
                    if (
                        tag.byte_length()
                        and t != p
                        and t not in ordinary
                        and t not in claimed_enums
                    ):
                        aliases.append(tag.copy())
                        claimed_enums[t] = True
                    claimed_enums[p] = True
                    names[v.decl_id] = EnumResolution(primary^, aliases^)
                case _:
                    pass
        var result = unit.copy()
        result.decls = List[Decl]()
        for d in decls:
            result.decls.append(rewrite_decl(d, names))
        return result^
