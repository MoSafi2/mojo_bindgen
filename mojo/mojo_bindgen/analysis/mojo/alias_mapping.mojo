from std.memory import ArcPointer
from ...ir import *
from ..common import mojo_ident
from .type_mapping import MapTypePass, exact_width_stdint_alias_type


def map_typedef_alias(
    c_name: String, aliased: CType, type_mapper: MapTypePass, doc: Optional[DocComment] = {}
) raises -> Optional[AliasDecl]:
    var name = mojo_ident(c_name)
    var exact = exact_width_stdint_alias_type(c_name)
    var mapped: MojoType
    if exact:
        mapped = MojoType.named_type(exact.value().copy())
    else:
        mapped = type_mapper.run(aliased)
    var kind = AliasKind.TYPE_ALIAS
    match mapped:
        case .mojo_function_ptr(_):
            kind = AliasKind.CALLBACK_SIGNATURE
        case .named_type(v):
            if v.name == name:
                return {}
        case _:
            pass
    return AliasDecl(name^, kind, type_value=ArcPointer(mapped^), doc=doc.copy())
