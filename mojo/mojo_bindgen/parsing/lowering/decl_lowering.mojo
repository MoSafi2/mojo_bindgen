"""Ordered declaration expansion and source-backed macro preservation."""
from clang.cindex import Cursor, CursorKind, TypeKind
from std.memory import ArcPointer
from ...ir import (
    Decl,
    CType,
    CConstExpr,
    Struct,
    Typedef,
    Enum,
    Enumerant,
    Const,
    CParam,
    Function,
    FunctionAttrs,
    InlineDisposition,
    GlobalVar,
    IntLiteral,
    IntType,
    MacroDecl,
    MacroDeclKind,
)
from ..._numbers import IntegerValue
from ..registry import RecordRegistry, RecordState, decl_id, is_record, anonymous
from ..frontend import children, tokens
from ..doc_comments import cursor_doc_comment
from .type_lowering import lower_type, TypeContext, calling_convention
from .record_lowering import lower_record
from .primitive import primitive, default_int
from .macro_fallback import ClangMacroFallback, needs_fallback
from .const_expr import ConstExprParser, ParsedConstExpr, fold, predefined, looks_function_like


def enum_integer(ref cursor: Cursor, underlying: IntType) raises -> IntegerValue:
    var value = cursor.enum_value()
    var name = underlying.int_kind.value()
    if name.startswith("U") or name == "CHAR_U" or name == "CHAR16" or name == "CHAR32":
        return IntegerValue.from_decimal(String(UInt64(value)))
    return IntegerValue(value)


def lower_decl(
    mut registry: RecordRegistry, mut parser: ConstExprParser, ref cursor: Cursor
) raises -> List[Decl]:
    var out = List[Decl]()
    var kind = cursor.kind()
    var name = cursor.spelling()
    if is_record(cursor):
        if cursor.is_definition() and name:
            out.append(Decl.struct_decl(lower_record(registry, cursor)))
        elif name and decl_id(cursor) not in registry.definitions:
            var record = Struct(
                decl_id(cursor),
                name.copy(),
                name.copy(),
                [],
                0,
                0,
                kind == CursorKind.UNION_DECL,
                False,
                False,
                doc=cursor_doc_comment(cursor),
            )
            if record.decl_id not in registry.states:
                registry.states[record.decl_id] = RecordState.declared(record.copy())
            out.append(Decl.struct_decl(record^))
    elif kind == CursorKind.FUNCTION_DECL:
        var t = cursor.type()
        var rt = t.result()
        var ret = lower_type(registry, rt, TypeContext.RETURN, cursor.copy())
        var params = List[CParam]()
        var noreturn = False
        for child in children(cursor):
            if child.kind() == CursorKind.PARM_DECL:
                var pt = child.type()
                params.append(
                    CParam(
                        child.spelling(),
                        ArcPointer(lower_type(registry, pt, TypeContext.PARAM, child.copy())),
                        cursor_doc_comment(child),
                    )
                )
            else:
                var attrs = tokens(child)
                if "_Noreturn" in attrs:
                    noreturn = True
        var body = tokens(cursor)
        var inline_disposition = InlineDisposition.NONE
        if "inline" in body or "__inline" in body or "__inline__" in body:
            inline_disposition = (
                InlineDisposition.EXTERN_INLINE if "extern" in body else InlineDisposition.INLINE
            )
        var variadic = t.kind() == TypeKind.FUNCTION_PROTO and t.is_function_variadic()
        if t.kind() == TypeKind.FUNCTION_NO_PROTO:
            registry.add_cursor_diag(
                "warning",
                cursor,
                "function has no prototype (K&R-style); parameters may be incomplete",
            )
        out.append(
            Decl.function(
                Function(
                    name.copy(),
                    name.copy(),
                    ArcPointer(ret^),
                    params^,
                    variadic,
                    decl_id(cursor),
                    calling_convention(t),
                    FunctionAttrs(inline_disposition, noreturn),
                    cursor_doc_comment(cursor),
                )
            )
        )
    elif kind == CursorKind.TYPEDEF_DECL:
        var t = cursor.underlying_typedef_type()
        var canonical = t.canonical()
        var aliased = lower_type(registry, t, TypeContext.TYPEDEF, cursor.copy())
        var resolved = lower_type(registry, canonical, TypeContext.TYPEDEF)
        out.append(
            Decl.typedef(
                Typedef(
                    decl_id(cursor),
                    name.copy(),
                    ArcPointer(aliased^),
                    ArcPointer(resolved^),
                    cursor_doc_comment(cursor),
                )
            )
        )
    elif kind == CursorKind.ENUM_DECL and cursor.is_definition():
        var t = cursor.enum_type()
        var p = primitive(t)
        var underlying = default_int()
        if p:
            match p.value():
                case .int_type(v):
                    underlying = v.copy()
                case _:
                    pass
        var enumerants = List[Enumerant]()
        for child in children(cursor):
            if child.kind() != CursorKind.ENUM_CONSTANT_DECL:
                continue
            var value = enum_integer(child, underlying)
            if anonymous(name):
                out.append(
                    Decl.const_decl(
                        Const(
                            child.spelling(),
                            ArcPointer(CType.int_type(underlying.copy())),
                            ArcPointer(CConstExpr.int_literal(IntLiteral(value^))),
                            cursor_doc_comment(child),
                        )
                    )
                )
            else:
                enumerants.append(
                    Enumerant(
                        child.spelling(),
                        child.spelling(),
                        value^,
                        decl_id(cursor),
                        cursor_doc_comment(child),
                    )
                )
        if not anonymous(name):
            var key = decl_id(cursor)
            out.append(
                Decl.enum_decl(
                    Enum(
                        key.copy(),
                        name.copy(),
                        name.copy(),
                        underlying^,
                        enumerants^,
                        is_anonymous="@EA@" in key,
                        doc=cursor_doc_comment(cursor),
                    )
                )
            )
    elif kind == CursorKind.VAR_DECL:
        var t = cursor.type()
        var initializer = Optional[ArcPointer[CConstExpr]]()
        var body = tokens(cursor)
        var after = List[String]()
        var found = False
        for token in body:
            if found:
                after.append(token.copy())
            elif token == "=":
                found = True
        if len(after) and after[len(after) - 1] == ";":
            _ = after.pop()
        var parsed = parser.parse_tokens(after)
        if parsed:
            initializer = ArcPointer(parsed.value().expr.copy())
        out.append(
            Decl.global_var(
                GlobalVar(
                    decl_id(cursor),
                    name.copy(),
                    name.copy(),
                    ArcPointer(lower_type(registry, t, TypeContext.PARAM)),
                    t.is_const_qualified(),
                    initializer^,
                    cursor_doc_comment(cursor),
                )
            )
        )
    return out^


def lower_macro(
    mut parser: ConstExprParser, ref cursor: Cursor, fallback: Optional[ClangMacroFallback] = {}
) raises -> Optional[MacroDecl]:
    var body = tokens(cursor)
    if len(body):
        _ = body.pop(0)
    if not len(body):
        return None
    var kind = MacroDeclKind.object_like_unsupported
    var diagnostic = Optional[String]("unsupported macro replacement list")
    var expr = Optional[ArcPointer[CConstExpr]]()
    var type = Optional[ArcPointer[CType]]()
    if len(body) == 1 and predefined(body[0]):
        kind = MacroDeclKind.predefined
        diagnostic = "predefined macro preserved without evaluation"
    elif cursor.is_macro_function_like() or looks_function_like(body):
        kind = MacroDeclKind.function_like_unsupported
        diagnostic = "function-like macros are preserved but not parsed"
    else:
        var parsed = parser.parse_tokens(body)
        if fallback and (not parsed or needs_fallback(parsed.value().expr)):
            var value = fallback.value().evaluate_integer(cursor.spelling())
            if value:
                var primitive = Optional[CType]()
                if parsed:
                    primitive = parsed.value().primitive.copy()
                if not primitive:
                    primitive = CType.int_type(parser.literal_resolver.for_suffix(""))
                parsed = ParsedConstExpr(
                    CConstExpr.int_literal(IntLiteral(value.value().copy())), primitive^
                )
        if parsed:
            kind = MacroDeclKind.object_like_supported
            var folded = fold(parsed.value().expr)
            expr = ArcPointer(folded.copy())
            if parsed.value().primitive:
                type = ArcPointer(parsed.value().primitive.value().copy())
            diagnostic = parsed.value().diagnostic.copy()
            parser.macro_values[cursor.spelling()] = ParsedConstExpr(
                folded^, parsed.value().primitive.copy(), diagnostic.copy()
            )
    return MacroDecl(
        cursor.spelling(), body^, kind, expr^, type^, diagnostic^, cursor_doc_comment(cursor)
    )
