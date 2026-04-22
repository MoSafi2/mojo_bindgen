"""Lower CIR constant expressions into Mojo-facing constant-expression IR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.common import mojo_float_literal_text, mojo_ident
from mojo_bindgen.ir import (
    BinaryExpr,
    CastExpr,
    CharLiteral,
    ConstExpr,
    FloatLiteral,
    IntLiteral,
    NullPtrLiteral,
    RefExpr,
    SizeOfExpr,
    StringLiteral,
    UnaryExpr,
)
from mojo_bindgen.mojo_ir import (
    MojoBinaryExpr,
    MojoCastExpr,
    MojoCharLiteral,
    MojoConstExpr,
    MojoFloatLiteral,
    MojoIntLiteral,
    MojoRefExpr,
    MojoSizeOfExpr,
    MojoStringLiteral,
    MojoUnaryExpr,
)
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass


class ConstExprLoweringError(ValueError):
    """Raised when a CIR constant expression cannot be lowered to MojoIR."""


@dataclass
class LowerConstExprPass:
    """Lower CIR constant expressions into Mojo-facing constant expressions."""

    type_lowering: LowerTypePass

    @staticmethod
    def _parse_float_literal(value: str) -> float:
        text = mojo_float_literal_text(value)
        lowered = text.lower()
        if lowered.startswith(("0x", "+0x", "-0x")):
            return float.fromhex(text)
        return float(text)

    def run(self, expr: ConstExpr) -> MojoConstExpr:
        if isinstance(expr, IntLiteral):
            return MojoIntLiteral(expr.value)
        if isinstance(expr, FloatLiteral):
            return MojoFloatLiteral(self._parse_float_literal(expr.value))
        if isinstance(expr, StringLiteral):
            return MojoStringLiteral(expr.value)
        if isinstance(expr, CharLiteral):
            return MojoCharLiteral(expr.value)
        if isinstance(expr, RefExpr):
            return MojoRefExpr(mojo_ident(expr.name))
        if isinstance(expr, UnaryExpr):
            return MojoUnaryExpr(op=expr.op, operand=self.run(expr.operand))
        if isinstance(expr, BinaryExpr):
            return MojoBinaryExpr(op=expr.op, lhs=self.run(expr.lhs), rhs=self.run(expr.rhs))
        if isinstance(expr, CastExpr):
            return MojoCastExpr(
                target=self.type_lowering.run(expr.target),
                expr=self.run(expr.expr),
            )
        if isinstance(expr, SizeOfExpr):
            return MojoSizeOfExpr(target=self.type_lowering.run(expr.target))
        if isinstance(expr, NullPtrLiteral):
            raise ConstExprLoweringError(
                "nullptr constants do not have a valid MojoIR literal form"
            )
        raise ConstExprLoweringError(
            f"unsupported CIR constant-expression node: {type(expr).__name__!r}"
        )


def lower_const_expr(expr: ConstExpr) -> MojoConstExpr:
    """Lower one CIR constant expression to MojoIR."""

    return LowerConstExprPass(type_lowering=LowerTypePass()).run(expr)


__all__ = [
    "ConstExprLoweringError",
    "LowerConstExprPass",
    "lower_const_expr",
]
