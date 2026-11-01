"""Opt-in Clang evaluation for macros outside the local expression subset."""
from clang.cindex import Index, UnsavedFile, CursorKind
from ..frontend import walk
from ...ir import CConstExpr
from ..._numbers import IntegerValue


def needs_fallback(expr: CConstExpr) -> Bool:
    match expr:
        case .c_ref_expr(_):
            return True
        case .c_unary_expr(v):
            return v.op == "!" or needs_fallback(v.operand.ptr()[])
        case .c_binary_expr(v):
            return (
                v.op == "&&"
                or v.op == "||"
                or needs_fallback(v.lhs.ptr()[])
                or needs_fallback(v.rhs.ptr()[])
            )
        case .c_cast_expr(v):
            return needs_fallback(v.expr.ptr()[])
        case _:
            return False


struct ClangMacroFallback(Copyable, Movable):
    var headers: List[String]
    var args: List[String]

    def __init__(out self, headers: List[String], args: List[String]):
        self.headers = headers.copy()
        self.args = args.copy()

    def evaluate_integer(self, name: String) -> Optional[IntegerValue]:
        from clang.cindex import Cursor

        var source = String()
        for header in self.headers:
            source += '#include "' + header.replace("\\", "\\\\").replace('"', '\\"') + '"\n'
        source += "enum { __mojo_bindgen_macro_value = (" + name + ") };\n"
        try:
            var index = Index.create()
            var tu = index.parse(
                "__mojo_bindgen_macro_fallback.c",
                self.args,
                [UnsavedFile("__mojo_bindgen_macro_fallback.c", source^)],
            )
            var root = tu.cursor()
            var nodes = List[Cursor]()
            walk(root, nodes)
            for cursor in nodes:
                if (
                    cursor.kind() == CursorKind.ENUM_CONSTANT_DECL
                    and cursor.spelling() == "__mojo_bindgen_macro_value"
                ):
                    var value = cursor.enum_value()
                    var shape = cursor.type()
                    var decl = shape.declaration()
                    if decl:
                        var kind = decl.value().enum_type().kind().as_c_uint()
                        if kind >= 4 and kind <= 12:
                            return IntegerValue.from_decimal(String(UInt64(value)))
                    return IntegerValue(value)
        except:
            pass
        return None
