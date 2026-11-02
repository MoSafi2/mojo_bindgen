from std.memory import ArcPointer
from ...ir import *
from ..common import mojo_ident
from .type_mapping import MapTypePass, exact_width_stdint_alias_type
from .mapping_support import stub_note
from ..facts.type_layout import type_layout, peel_layout_wrappers
from ..facts.representation import target_layout


def _integer_alias(name: String, t: CType) -> Bool:
    var core = peel_layout_wrappers(t)
    if case .int_type(v) = core:
        match v.int_kind:
            case .CHAR_S | .SCHAR | .SHORT | .INT | .LONG | .LONGLONG | .INT128:
                return name.startswith("Int")
            case .CHAR_U | .UCHAR | .USHORT | .UINT | .ULONG | .ULONGLONG | .UINT128:
                return name.startswith("UInt")
            case _:
                return False
    return False


def map_typedef_alias(
    c_name: String, aliased: CType, type_mapper: MapTypePass, doc: Optional[DocComment] = {}
) raises -> Optional[AliasDecl]:
    var name = mojo_ident(c_name)
    var exact = exact_width_stdint_alias_type(c_name)
    var mapped: MojoType
    var source_shape = type_layout(aliased)
    if (
        exact
        and _integer_alias(exact.value().name, aliased)
        and source_shape
        and source_shape
        == target_layout(MojoType.named_type(exact.value().copy()), type_mapper.queries)
    ):
        mapped = MojoType.named_type(exact.value().copy())
    else:
        mapped = type_mapper.run(aliased)
    if case .builtin_type(v) = mapped:
        if v.name == MojoBuiltin.UNSUPPORTED:
            var notes: List[MappingNote] = [
                stub_note("alias type has no supported storage representation")
            ]
            return AliasDecl(name, AliasKind.TYPE_ALIAS, diagnostics=notes^, doc=doc.copy())
    var kind = AliasKind.TYPE_ALIAS
    match mapped:
        case .mojo_function_ptr(_):
            kind = AliasKind.CALLBACK_SIGNATURE
        case .named_type(v):
            if v.name == name:
                return {}
        case _:
            pass
    var notes = List[MappingNote]()
    if case .c_function_ptr(_) = aliased:
        if kind != AliasKind.CALLBACK_SIGNATURE:
            notes.append(stub_note("callback signature is unsupported; opaque address emitted"))
    return AliasDecl(
        name^, kind, type_value=ArcPointer(mapped^), diagnostics=notes^, doc=doc.copy()
    )
