"""Lower C macro declarations into MojoIR aliases or diagnostic placeholders."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.mojo.const_lowering import ConstExprLoweringError, LowerConstExprPass
from mojo_bindgen.analysis.mojo.const_value_lowering import typed_const_value
from mojo_bindgen.analysis.mojo.lowering_support import lowering_note, stub_note
from mojo_bindgen.analysis.mojo.type_lowering import LowerTypePass
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    BinaryExpr,
    CallExpr,
    CastExpr,
    ConstExpr,
    MacroDecl,
    NullPtrLiteral,
    RefExpr,
    SizeOfExpr,
    UnaryExpr,
)


@dataclass
class MacroLowerer:
    """Lower macro declarations while tracking already-emitted constant names."""

    const_lowerer: LowerConstExprPass
    type_lowerer: LowerTypePass
    emitted_const_names: set[str]

    def lower(self, decl: MacroDecl) -> AliasDecl | None:
        if decl.kind == "empty":
            return None

        name = mojo_ident(decl.name)
        if name in self.emitted_const_names:
            if isinstance(decl.expr, RefExpr) and mojo_ident(decl.expr.name) == name:
                return None
            return self._comment_alias(
                decl,
                f"macro {decl.name}: macro name conflicts with an emitted constant",
            )

        if decl.expr is not None and decl.type is not None:
            lowered = self._lower_value_macro(decl, name)
            if lowered is not None:
                return lowered

        return self._placeholder_alias(decl)

    def _lower_value_macro(self, decl: MacroDecl, name: str) -> AliasDecl | None:
        assert decl.expr is not None
        assert decl.type is not None

        blocker = self._emit_blocker(decl.expr)
        if blocker is not None:
            return self._comment_alias(decl, f"macro {decl.name}: {blocker}")

        try:
            value = self.const_lowerer.run(decl.expr)
        except ConstExprLoweringError:
            if isinstance(decl.expr, NullPtrLiteral):
                return self._comment_alias(
                    decl,
                    f"macro {decl.name}: null pointer macro is not emitted directly",
                )
            return None

        self.emitted_const_names.add(name)
        return AliasDecl(
            name=name,
            kind=AliasKind.MACRO_VALUE,
            const_value=typed_const_value(
                value,
                decl.type,
                type_lowerer=self.type_lowerer,
            ),
            doc=decl.doc,
        )

    def _emit_blocker(self, expr: ConstExpr) -> str | None:
        if isinstance(expr, NullPtrLiteral):
            return "null pointer macro is not emitted directly"
        if isinstance(expr, RefExpr):
            name = mojo_ident(expr.name)
            if name not in self.emitted_const_names:
                return (
                    "macro expression references a non-emitted or later macro constant "
                    f"{expr.name!r}"
                )
            return None
        if isinstance(expr, UnaryExpr):
            if expr.op == "!":
                return "C logical operator '!' is not emitted directly"
            return self._emit_blocker(expr.operand)
        if isinstance(expr, BinaryExpr):
            if expr.op in {"&&", "||"}:
                return f"C logical operator {expr.op!r} is not emitted directly"
            return self._emit_blocker(expr.lhs) or self._emit_blocker(expr.rhs)
        if isinstance(expr, CastExpr):
            return self._emit_blocker(expr.expr)
        if isinstance(expr, (SizeOfExpr, CallExpr)):
            return None
        return None

    def _placeholder_alias(self, decl: MacroDecl) -> AliasDecl:
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.MACRO_VALUE,
            diagnostics=(
                self._comment_notes(decl, f"macro {decl.name}: {decl.diagnostic}")
                if decl.diagnostic
                else [stub_note("macro lowering is incomplete; placeholder alias emitted")]
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

    def _comment_notes(self, decl: MacroDecl, message: str):
        return [
            lowering_note(message, category="macro_comment"),
            lowering_note(
                f"define {decl.name} {' '.join(decl.tokens)}",
                category="macro_comment",
            ),
        ]


__all__ = [
    "MacroLowerer",
]
