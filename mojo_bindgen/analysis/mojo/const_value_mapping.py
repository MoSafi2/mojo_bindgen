"""Helpers for typed MojoIR constant values."""

from __future__ import annotations

from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
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
    type_mapper: MapTypePass,
) -> ConstExpr:
    """Apply Mojo-facing type coercions needed for emitted constant aliases."""

    mapped_type = type_mapper.run(decl_type)
    if isinstance(mapped_type, BuiltinType) and mapped_type.name in _MOJO_INT_TYPES:
        return _coerce_integral_const(value, mapped_type)
    return value


def _coerce_integral_const(
    value: ConstExpr,
    mapped_type: BuiltinType,
) -> ConstExpr:
    if isinstance(value, IntLiteral):
        return CastExpr(target=mapped_type, expr=value)
    if isinstance(value, UnaryExpr):
        return UnaryExpr(
            op=value.op,
            operand=_coerce_integral_const(value.operand, mapped_type),
        )
    if isinstance(value, BinaryExpr):
        return BinaryExpr(
            op=value.op,
            lhs=_coerce_integral_const(value.lhs, mapped_type),
            rhs=_coerce_integral_const(value.rhs, mapped_type),
        )
    return value


__all__ = [
    "typed_const_value",
]
