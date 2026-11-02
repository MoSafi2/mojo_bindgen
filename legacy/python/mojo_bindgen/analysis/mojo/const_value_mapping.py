"""Helpers for typed MojoIR constant values."""

from __future__ import annotations

from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    _MOJO_INT_TYPES,
    BuiltinType,
    CType,
    IntLiteral,
    MojoBinaryExpr,
    MojoCastExpr,
    MojoConstExpr,
    MojoUnaryExpr,
)


def typed_const_value(
    value: MojoConstExpr,
    decl_type: CType,
    *,
    type_mapper: MapTypePass,
) -> MojoConstExpr:
    """Apply Mojo-facing type coercions needed for emitted constant aliases."""

    if not type_mapper.value_supported(decl_type):
        from .const_expr_mapping import ConstExprMappingError

        raise ConstExprMappingError("constant type has no supported Mojo value representation")
    mapped_type = type_mapper.run(decl_type)
    if isinstance(mapped_type, BuiltinType) and mapped_type.name in _MOJO_INT_TYPES:
        return _coerce_integral_const(value, mapped_type)
    return value


def _coerce_integral_const(
    value: MojoConstExpr,
    mapped_type: BuiltinType,
) -> MojoConstExpr:
    if isinstance(value, IntLiteral):
        return MojoCastExpr(target=mapped_type, expr=value)
    if isinstance(value, MojoUnaryExpr):
        return MojoUnaryExpr(
            op=value.op,
            operand=_coerce_integral_const(value.operand, mapped_type),
        )
    if isinstance(value, MojoBinaryExpr):
        return MojoBinaryExpr(
            op=value.op,
            lhs=_coerce_integral_const(value.lhs, mapped_type),
            rhs=_coerce_integral_const(value.rhs, mapped_type),
        )
    return value


__all__ = [
    "typed_const_value",
]
