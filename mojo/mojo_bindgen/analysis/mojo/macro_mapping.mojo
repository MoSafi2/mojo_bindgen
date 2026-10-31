from std.memory import ArcPointer
from ...ir import *
from ..common import mojo_ident, quoted
from ..traversal import expression_children
from .type_mapping import MapTypePass
from .const_expr_mapping import MapConstExprPass
from .const_value_mapping import typed_const_value
from .mapping_support import mapping_note, stub_note


def has_null(expr: CConstExpr) -> Bool:
    match expr:
        case .c_null_ptr_literal(_):
            return True
        case _:
            pass
    for child in expression_children(expr):
        if has_null(child.ptr()[]):
            return True
    return False


def _blocker(expr: CConstExpr, emitted: Dict[String, Bool]) -> Optional[String]:
    match expr:
        case .c_null_ptr_literal(_):
            return String("null pointer macro is not emitted directly")
        case .c_ref_expr(v):
            if mojo_ident(v.name) not in emitted:
                return String(
                    "macro expression references a non-emitted or later macro constant "
                    + quoted(v.name)
                )
        case .c_unary_expr(v):
            if v.op == "!":
                return String("C logical operator '!' is not emitted directly")
            return _blocker(v.operand.ptr()[], emitted)
        case .c_binary_expr(v):
            if v.op == "&&" or v.op == "||":
                return String("C logical operator " + quoted(v.op) + " is not emitted directly")
            var left = _blocker(v.lhs.ptr()[], emitted)
            return left^ if left else _blocker(v.rhs.ptr()[], emitted)
        case .c_cast_expr(v):
            return _blocker(v.expr.ptr()[], emitted)
        case _:
            pass
    return {}


def _comment(decl: MacroDecl, message: String) -> AliasDecl:
    var notes = List[MappingNote]()
    notes.append(mapping_note(message, "macro_comment"))
    var tokens = String()
    for i in range(len(decl.tokens)):
        if i:
            tokens += " "
        tokens += decl.tokens[i]
    notes.append(mapping_note("define " + decl.name + " " + tokens, "macro_comment"))
    return AliasDecl(
        mojo_ident(decl.name), AliasKind.MACRO_VALUE, diagnostics=notes^, doc=decl.doc.copy()
    )


@fieldwise_init
struct MacroMapper(Copyable, Movable):
    var const_expr_mapper: MapConstExprPass
    var type_mapper: MapTypePass

    def map(self, decl: MacroDecl, mut emitted: Dict[String, Bool]) raises -> Optional[AliasDecl]:
        if decl.kind == MacroDeclKind.empty:
            return {}
        var name = mojo_ident(decl.name)
        if name in emitted:
            if decl.expr:
                match decl.expr.value().ptr()[]:
                    case .c_ref_expr(v):
                        if mojo_ident(v.name) == name:
                            return {}
                    case _:
                        pass
            return _comment(
                decl, "macro " + decl.name + ": macro name conflicts with an emitted constant"
            )
        if decl.expr and decl.type:
            var blocker = _blocker(decl.expr.value().ptr()[], emitted)
            if blocker:
                return _comment(decl, "macro " + decl.name + ": " + blocker.value())
            if not has_null(decl.expr.value().ptr()[]):
                var value = self.const_expr_mapper.run(decl.expr.value().ptr()[])
                var typed = typed_const_value(value, decl.type.value().ptr()[], self.type_mapper)
                emitted[name] = True
                return AliasDecl(
                    name^,
                    AliasKind.MACRO_VALUE,
                    const_value=ArcPointer(typed^),
                    doc=decl.doc.copy(),
                )
        if decl.diagnostic and decl.diagnostic.value().byte_length():
            return _comment(decl, "macro " + decl.name + ": " + decl.diagnostic.value())
        var notes = List[MappingNote]()
        notes.append(stub_note("macro mapping is incomplete; placeholder alias emitted"))
        return AliasDecl(name^, AliasKind.MACRO_VALUE, diagnostics=notes^, doc=decl.doc.copy())
