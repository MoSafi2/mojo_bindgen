"""Map C macro declarations into MojoIR aliases or diagnostic placeholders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.mojo.const_expr_mapping import ConstExprMappingError, MapConstExprPass
from mojo_bindgen.analysis.mojo.const_value_mapping import typed_const_value
from mojo_bindgen.analysis.mojo.mapping_support import mapping_note, stub_note
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    CBinaryExpr,
    CCallExpr,
    CCastExpr,
    CConstExpr,
    CFloatLiteral,
    CharLiteral,
    CNullPtrLiteral,
    CRefExpr,
    CSizeOfExpr,
    CUnaryExpr,
    IntLiteral,
    MacroDecl,
    MappingNote,
    StringLiteral,
)


@dataclass
class MacroMapper:
    """Map macro declarations while tracking already-emitted constant names."""

    const_expr_mapper: MapConstExprPass
    type_mapper: MapTypePass
    emitted_const_names: set[str]

    def map(self, decl: MacroDecl) -> AliasDecl | None:
        if decl.kind == "empty":
            return None

        name = mojo_ident(decl.name)
        if name in self.emitted_const_names:
            if isinstance(decl.expr, CRefExpr) and mojo_ident(decl.expr.name) == name:
                return None
            return self._comment_alias(
                decl,
                f"macro {decl.name}: macro name conflicts with an emitted constant",
            )

        if decl.expr is not None and decl.type is not None:
            mapped = self._map_value_macro(decl, name)
            if mapped is not None:
                return mapped

        return self._placeholder_alias(decl)

    def _map_value_macro(self, decl: MacroDecl, name: str) -> AliasDecl | None:
        assert decl.expr is not None
        assert decl.type is not None

        blocker = self._emit_blocker(decl.expr)
        if blocker is not None:
            return self._comment_alias(decl, f"macro {decl.name}: {blocker}")

        try:
            value = self.const_expr_mapper.run(decl.expr)
        except ConstExprMappingError:
            if isinstance(decl.expr, CNullPtrLiteral):
                return self._comment_alias(
                    decl,
                    f"macro {decl.name}: null pointer macro is not emitted directly",
                )
            return None

        typed_value = typed_const_value(value, decl.type, type_mapper=self.type_mapper)
        self.emitted_const_names.add(name)
        return AliasDecl(
            name=name,
            kind=AliasKind.MACRO_VALUE,
            const_value=typed_value,
            doc=decl.doc,
        )

    def _emit_blocker(self, expr: CConstExpr) -> str | None:
        if isinstance(expr, CNullPtrLiteral):
            return "null pointer macro is not emitted directly"
        if isinstance(expr, CRefExpr):
            name = mojo_ident(expr.name)
            if name not in self.emitted_const_names:
                return (
                    "macro expression references a non-emitted or later macro constant "
                    f"{expr.name!r}"
                )
            return None
        if isinstance(expr, CUnaryExpr):
            if expr.op == "!":
                return "C logical operator '!' is not emitted directly"
            return self._emit_blocker(expr.operand)
        if isinstance(expr, CBinaryExpr):
            if expr.op in {"&&", "||"}:
                return f"C logical operator {expr.op!r} is not emitted directly"
            return self._emit_blocker(expr.lhs) or self._emit_blocker(expr.rhs)
        if isinstance(expr, CCastExpr):
            return self._emit_blocker(expr.expr)
        if isinstance(
            expr, (CSizeOfExpr, CCallExpr, IntLiteral, CFloatLiteral, StringLiteral, CharLiteral)
        ):
            return None
        assert_never(expr)

    def _placeholder_alias(self, decl: MacroDecl) -> AliasDecl:
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.MACRO_VALUE,
            diagnostics=(
                self._comment_notes(decl, f"macro {decl.name}: {decl.diagnostic}")
                if decl.diagnostic
                else (stub_note("macro mapping is incomplete; placeholder alias emitted"),)
            ),
            doc=decl.doc,
        )

    def _comment_alias(self, decl: MacroDecl, message: str) -> AliasDecl:
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.MACRO_VALUE,
            diagnostics=self._comment_notes(decl, message),
            doc=decl.doc,
        )

    def _comment_notes(self, decl: MacroDecl, message: str) -> tuple[MappingNote, ...]:
        return (
            mapping_note(message, category="macro_comment"),
            mapping_note(
                f"define {decl.name} {' '.join(decl.tokens)}",
                category="macro_comment",
            ),
        )


__all__ = [
    "MacroMapper",
]
