"""Map CIR constant expressions into Mojo-facing constant-expression IR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.common import mojo_float_literal_text, mojo_ident
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    BinaryExpr,
    CallExpr,
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


class ConstExprMappingError(ValueError):
    """Raised when a CIR constant expression cannot be mapped to MojoIR."""


@dataclass
class MapConstExprPass:
    """Map CIR constant expressions into Mojo-facing constant expressions."""

    type_mapping: MapTypePass

    @staticmethod
    def _parse_float_literal(value: str | float) -> float:
        text = mojo_float_literal_text(str(value))
        mapped = text.lower()
        if mapped.startswith(("0x", "+0x", "-0x")):
            return float.fromhex(text)
        return float(text)

    def run(self, expr: ConstExpr) -> ConstExpr:
        if isinstance(expr, IntLiteral):
            return expr
        if isinstance(expr, FloatLiteral):
            return FloatLiteral(self._parse_float_literal(expr.value))
        if isinstance(expr, StringLiteral):
            return expr
        if isinstance(expr, CharLiteral):
            return expr
        if isinstance(expr, RefExpr):
            return RefExpr(mojo_ident(expr.name))
        if isinstance(expr, UnaryExpr):
            return UnaryExpr(op=expr.op, operand=self.run(expr.operand))
        if isinstance(expr, BinaryExpr):
            return BinaryExpr(op=expr.op, lhs=self.run(expr.lhs), rhs=self.run(expr.rhs))
        if isinstance(expr, CastExpr):
            return CastExpr(
                target=self.type_mapping.run(expr.target),
                expr=self.run(expr.expr),
            )
        if isinstance(expr, SizeOfExpr):
            return SizeOfExpr(target=self.type_mapping.run(expr.target))
        if isinstance(expr, CallExpr):
            return CallExpr(
                callee=self.run(expr.callee),
                args=[self.run(arg) for arg in expr.args],
            )
        if isinstance(expr, NullPtrLiteral):
            raise ConstExprMappingError("nullptr constants do not have a valid MojoIR literal form")
        raise ConstExprMappingError(
            f"unsupported CIR constant-expression node: {type(expr).__name__!r}"
        )


def map_const_expr(expr: ConstExpr) -> ConstExpr:
    """Map one CIR constant expression to MojoIR."""

    return MapConstExprPass(type_mapping=MapTypePass()).run(expr)


__all__ = [
    "ConstExprMappingError",
    "MapConstExprPass",
    "map_const_expr",
]
