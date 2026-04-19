"""Top-level declaration lowering for the parser package.

This module assembles top-level IR declarations. It delegates type conversion,
record lowering, and constant-expression parsing to narrower collaborators and
should stay thin.
"""

from __future__ import annotations

import clang.cindex as cx

from mojo_bindgen.ir import (
    Const,
    Decl,
    Enum,
    Enumerant,
    Function,
    GlobalVar,
    IntLiteral,
    MacroDecl,
    Param,
    Typedef,
)
from mojo_bindgen.parsing.frontend import ClangCompat
from mojo_bindgen.parsing.frontend import ClangFrontend
from mojo_bindgen.parsing.diagnostics import ParserDiagnosticSink
from mojo_bindgen.parsing.registry import RecordRegistry
from mojo_bindgen.parsing.lowering.const_expr import ConstExprParser
from mojo_bindgen.parsing.lowering.macro_env import collect_object_like_macro_env
from mojo_bindgen.parsing.lowering.primitive import PrimitiveResolver, default_signed_int_primitive
from mojo_bindgen.parsing.lowering.record_lowering import RecordLowerer
from mojo_bindgen.parsing.lowering.type_lowering import TypeContext, TypeLowerer


class DeclLowerer:
    """Lower top-level declarations into IR declarations."""

    def __init__(
        self,
        *,
        frontend: ClangFrontend,
        tu: cx.TranslationUnit,
        registry: RecordRegistry,
        diagnostics: ParserDiagnosticSink,
        primitive_resolver: PrimitiveResolver,
        type_lowerer: TypeLowerer,
        record_lowerer: RecordLowerer,
        const_expr_parser: ConstExprParser,
        compat: ClangCompat,
    ) -> None:
        self.frontend = frontend
        self.tu = tu
        self.registry = registry
        self.diagnostics = diagnostics
        self.primitive_resolver = primitive_resolver
        self.type_lowerer = type_lowerer
        self.record_lowerer = record_lowerer
        self.const_expr_parser = const_expr_parser
        self.compat = compat

    def lower_top_level_decl(self, cursor: cx.Cursor) -> list[Decl] | Decl | None:
        """Lower one primary-file top-level cursor."""
        k = cursor.kind
        if k == cx.CursorKind.FUNCTION_DECL:
            return self._build_function(cursor)
        if k in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            return self.record_lowerer.lower_top_level_record(cursor)
        if k == cx.CursorKind.ENUM_DECL:
            if not cursor.is_definition():
                return None
            if self._is_anonymous_enum(cursor):
                return self._anonymous_enum_as_consts(cursor)
            return self._build_enum(cursor)
        if k == cx.CursorKind.TYPEDEF_DECL:
            return self._build_typedef(cursor)
        if k == cx.CursorKind.VAR_DECL:
            return self._build_global_var(cursor)
        return None

    def collect_macros(self) -> list[Decl]:
        """Lower all primary-file macro definitions into preserved IR nodes."""
        macro_env = collect_object_like_macro_env(self.tu)
        out: list[Decl] = []
        for cursor in self.tu.cursor.walk_preorder():
            if cursor.kind != cx.CursorKind.MACRO_DEFINITION:
                continue
            if not self.frontend.is_primary_file_cursor(cursor):
                continue
            parsed = self.const_expr_parser.parse_macro(cursor, macro_env)
            out.append(
                MacroDecl(
                    name=cursor.spelling,
                    tokens=parsed.tokens,
                    kind=parsed.kind,
                    expr=parsed.expr,
                    type=parsed.primitive,
                    diagnostic=parsed.diagnostic,
                )
            )
        return out

    def _build_function(self, cursor: cx.Cursor) -> Function:
        fn_type = cursor.type
        ret_ir = self.type_lowerer.lower(fn_type.get_result(), TypeContext.RETURN)
        params: list[Param] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PARM_DECL:
                param_type = self.type_lowerer.lower(child.type, TypeContext.PARAM)
                params.append(Param(name=child.spelling, type=param_type))

        is_variadic = fn_type.kind == cx.TypeKind.FUNCTIONPROTO and fn_type.is_function_variadic()
        if fn_type.kind == cx.TypeKind.FUNCTIONNOPROTO:
            self.diagnostics.add_cursor_diag(
                "warning",
                cursor,
                "function has no prototype (K&R-style); parameters may be incomplete",
            )
        return Function(
            decl_id=self.registry.decl_id_for_cursor(cursor),
            name=cursor.spelling,
            link_name=cursor.spelling,
            ret=ret_ir,
            params=params,
            is_variadic=is_variadic,
            calling_convention=self.compat.get_calling_convention(fn_type),
            is_noreturn=self._function_is_noreturn(cursor),
        )

    @staticmethod
    def _function_is_noreturn(cursor: cx.Cursor) -> bool:
        """Return whether a function declaration carries a noreturn attribute."""
        for child in cursor.get_children():
            kind_name = child.kind.name
            if kind_name in {"C11_NO_RETURN_ATTR", "NORETURN_ATTR"}:
                return True
            if child.kind == cx.CursorKind.UNEXPOSED_ATTR:
                tokens = [token.spelling for token in child.get_tokens()]
                if tokens == ["_Noreturn"]:
                    return True
        return False

    def _anonymous_enum_as_consts(self, cursor: cx.Cursor) -> list[Const]:
        underlying = self.primitive_resolver.resolve_primitive(cursor.enum_type)
        if underlying is None:
            underlying = default_signed_int_primitive()
        out: list[Const] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.ENUM_CONSTANT_DECL:
                out.append(Const(name=child.spelling, type=underlying, expr=IntLiteral(child.enum_value)))
        return out

    def _build_enum(self, cursor: cx.Cursor) -> Enum | None:
        c_name = cursor.spelling
        if not c_name:
            return None
        underlying = self.primitive_resolver.resolve_primitive(cursor.enum_type)
        if underlying is None:
            underlying = default_signed_int_primitive()
        enumerants: list[Enumerant] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.ENUM_CONSTANT_DECL:
                enumerants.append(
                    Enumerant(name=child.spelling, c_name=child.spelling, value=child.enum_value)
                )
        return Enum(
            decl_id=self.registry.decl_id_for_cursor(cursor),
            name=c_name,
            c_name=c_name,
            underlying=underlying,
            enumerants=enumerants,
        )

    def _build_typedef(self, cursor: cx.Cursor) -> Typedef:
        name = cursor.spelling
        ut = cursor.underlying_typedef_type
        aliased = self.type_lowerer.lower(ut, TypeContext.TYPEDEF)
        canonical = self.type_lowerer.lower(ut.get_canonical(), TypeContext.TYPEDEF)
        return Typedef(
            decl_id=self.registry.decl_id_for_cursor(cursor),
            name=name,
            aliased=aliased,
            canonical=canonical,
        )

    @staticmethod
    def _is_anonymous_enum(cursor: cx.Cursor) -> bool:
        spelling = cursor.spelling
        return not spelling or "(unnamed at " in spelling or "(anonymous at " in spelling

    def _build_global_var(self, cursor: cx.Cursor) -> GlobalVar:
        parsed = self.const_expr_parser.parse_initializer(cursor)
        return GlobalVar(
            decl_id=self.registry.decl_id_for_cursor(cursor),
            name=cursor.spelling,
            link_name=cursor.spelling,
            type=self.type_lowerer.lower(cursor.type, TypeContext.PARAM),
            is_const=cursor.type.is_const_qualified(),
            initializer=None if parsed is None else parsed.expr,
        )
