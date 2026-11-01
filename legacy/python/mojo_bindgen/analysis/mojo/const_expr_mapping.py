"""Map source constant expressions into the distinct Mojo expression family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from mojo_bindgen.analysis.common import mojo_float_literal_text, mojo_ident
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
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
    MojoBinaryExpr,
    MojoCallExpr,
    MojoCastExpr,
    MojoConstExpr,
    MojoFloatLiteral,
    MojoRefExpr,
    MojoSizeOfExpr,
    MojoUnaryExpr,
    StringLiteral,
)


class ConstExprMappingError(ValueError):
    """The source expression has no supported target form."""


@dataclass(frozen=True)
class MapConstExprPass:
    type_mapping: MapTypePass

    @staticmethod
    def _parse_float_literal(value: str) -> float:
        text = mojo_float_literal_text(value)
        if text.lower().startswith(("0x", "+0x", "-0x")):
            return float.fromhex(text)
        return float(text)

    def run(self, expr: CConstExpr) -> MojoConstExpr:
        match expr:
            case IntLiteral() | StringLiteral() | CharLiteral():
                return expr
            case CFloatLiteral():
                return MojoFloatLiteral(self._parse_float_literal(expr.spelling))
            case CRefExpr():
                return MojoRefExpr(mojo_ident(expr.name))
            case CUnaryExpr():
                return MojoUnaryExpr(expr.op, self.run(expr.operand))
            case CBinaryExpr():
                return MojoBinaryExpr(expr.op, self.run(expr.lhs), self.run(expr.rhs))
            case CCastExpr():
                return MojoCastExpr(self.type_mapping.run(expr.target), self.run(expr.expr))
            case CSizeOfExpr():
                return MojoSizeOfExpr(self.type_mapping.run(expr.target))
            case CCallExpr():
                return MojoCallExpr(
                    self.run(expr.callee), tuple(self.run(arg) for arg in expr.args)
                )
            case CNullPtrLiteral():
                raise ConstExprMappingError(
                    "nullptr constants do not have a valid MojoIR literal form"
                )
        assert_never(expr)


def map_const_expr(expr: CConstExpr, *, type_mapper: MapTypePass) -> MojoConstExpr:
    return MapConstExprPass(type_mapper).run(expr)


__all__ = ["MapConstExprPass", "ConstExprMappingError", "map_const_expr"]
