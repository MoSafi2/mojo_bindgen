"""Unit tests for CIR -> MojoIR constant-expression lowering."""

from __future__ import annotations

from mojo_bindgen.analysis.mojo.const_lowering import lower_const_expr
from mojo_bindgen.ir import (
    BinaryExpr,
    BuiltinType,
    CastExpr,
    FloatLiteral,
    IntKind,
    IntLiteral,
    IntType,
    MojoBuiltin,
    RefExpr,
    SizeOfExpr,
)


def test_lower_const_expr_maps_binary_ref_cast_and_sizeof_nodes() -> None:
    c_int = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)

    assert lower_const_expr(BinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2))) == (
        BinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2))
    )
    assert lower_const_expr(RefExpr(name="VALUE")) == RefExpr(name="VALUE")
    assert lower_const_expr(CastExpr(target=c_int, expr=IntLiteral(7))) == CastExpr(
        target=BuiltinType(MojoBuiltin.C_INT),
        expr=IntLiteral(7),
    )
    assert lower_const_expr(SizeOfExpr(target=c_int)) == SizeOfExpr(
        target=BuiltinType(MojoBuiltin.C_INT)
    )


def test_lower_const_expr_parses_decimal_and_hex_float_literals() -> None:
    assert lower_const_expr(FloatLiteral("1.25f")) == FloatLiteral(1.25)
    assert lower_const_expr(FloatLiteral("0x1.0p4")) == FloatLiteral(16.0)
