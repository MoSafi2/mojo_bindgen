"""Map source constant expressions into the distinct Mojo expression family."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from mojo_bindgen.analysis.common import mojo_float_literal_text, mojo_ident
from mojo_bindgen.analysis.facts.type_layout import type_size
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
    FloatFormat,
    FloatKind,
    IntLiteral,
    MojoBinaryExpr,
    MojoCallExpr,
    MojoCastExpr,
    MojoConstExpr,
    MojoFloatLiteral,
    MojoRefExpr,
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
                if (
                    expr.spelling.lower().endswith("l")
                    and self.type_mapping.queries.float_format(FloatKind.LONG_DOUBLE)
                    != FloatFormat.BINARY64
                ):
                    raise ConstExprMappingError(
                        "extended floating literal has no supported Mojo value representation"
                    )
                return MojoFloatLiteral(self._parse_float_literal(expr.spelling))
            case CRefExpr():
                return MojoRefExpr(mojo_ident(expr.name))
            case CUnaryExpr():
                return MojoUnaryExpr(expr.op, self.run(expr.operand))
            case CBinaryExpr():
                return MojoBinaryExpr(expr.op, self.run(expr.lhs), self.run(expr.rhs))
            case CCastExpr():
                if not self.type_mapping.value_supported(expr.target):
                    raise ConstExprMappingError(
                        "cast target has no supported Mojo value representation"
                    )
                return MojoCastExpr(self.type_mapping.run(expr.target), self.run(expr.expr))
            case CSizeOfExpr():
                size = type_size(expr.target)
                if size is None:
                    raise ConstExprMappingError("sizeof target has no known source size")
                return IntLiteral(size)
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
