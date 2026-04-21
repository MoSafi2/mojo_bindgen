"""Unit tests for CIR -> MojoIR constant-expression lowering."""

from __future__ import annotations

from mojo_bindgen.ir import BinaryExpr, CastExpr, IntKind, IntLiteral, IntType, RefExpr, SizeOfExpr
from mojo_bindgen.mojo_ir import (
    BuiltinType,
    MojoBinaryExpr,
    MojoBuiltin,
    MojoCastExpr,
    MojoIntLiteral,
    MojoRefExpr,
    MojoSizeOfExpr,
)
from mojo_bindgen.new_analysis.const_lowering import lower_const_expr


def test_lower_const_expr_maps_binary_ref_cast_and_sizeof_nodes() -> None:
    c_int = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)

    assert lower_const_expr(BinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2))) == (
        MojoBinaryExpr(op="+", lhs=MojoIntLiteral(1), rhs=MojoIntLiteral(2))
    )
    assert lower_const_expr(RefExpr(name="VALUE")) == MojoRefExpr(name="VALUE")
    assert lower_const_expr(CastExpr(target=c_int, expr=IntLiteral(7))) == MojoCastExpr(
        target=BuiltinType(MojoBuiltin.C_INT),
        expr=MojoIntLiteral(7),
    )
    assert lower_const_expr(SizeOfExpr(target=c_int)) == MojoSizeOfExpr(
        target=BuiltinType(MojoBuiltin.C_INT)
    )
