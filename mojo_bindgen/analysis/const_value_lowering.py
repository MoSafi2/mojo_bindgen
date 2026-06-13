"""Helpers for typed MojoIR constant values."""

from __future__ import annotations

from mojo_bindgen.analysis.type_lowering import LowerTypePass
from mojo_bindgen.ir import (
    _MOJO_INT_TYPES,
    BinaryExpr,
    BuiltinType,
    CastExpr,
    ConstExpr,
    IntLiteral,
    Type,
    UnaryExpr,
)


def typed_const_value(
    value: ConstExpr,
    decl_type: Type,
    *,
    type_lowerer: LowerTypePass,
) -> ConstExpr:
    """Apply Mojo-facing type coercions needed for emitted constant aliases."""

    lowered_type = type_lowerer.run(decl_type)
    if isinstance(lowered_type, BuiltinType) and lowered_type.name in _MOJO_INT_TYPES:
        return _coerce_integral_const(value, lowered_type)
    return value


def _coerce_integral_const(
    value: ConstExpr,
    lowered_type: BuiltinType,
) -> ConstExpr:
    if isinstance(value, IntLiteral):
        return CastExpr(target=lowered_type, expr=value)
    if isinstance(value, UnaryExpr):
        return UnaryExpr(
            op=value.op,
            operand=_coerce_integral_const(value.operand, lowered_type),
        )
    if isinstance(value, BinaryExpr):
        return BinaryExpr(
            op=value.op,
            lhs=_coerce_integral_const(value.lhs, lowered_type),
            rhs=_coerce_integral_const(value.rhs, lowered_type),
        )
    return value


__all__ = [
    "typed_const_value",
]
