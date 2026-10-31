"""Unit tests for CIR -> MojoIR constant-expression mapping."""

from __future__ import annotations

from mojo_bindgen.analysis.mojo.const_expr_mapping import map_const_expr
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    BuiltinType,
    CBinaryExpr,
    CCastExpr,
    CFloatLiteral,
    CRefExpr,
    CSizeOfExpr,
    IntKind,
    IntLiteral,
    IntType,
    MojoBinaryExpr,
    MojoBuiltin,
    MojoCastExpr,
    MojoFloatLiteral,
    MojoRefExpr,
    MojoSizeOfExpr,
)
from tests.bindgen_helpers import DEFAULT_TARGET_QUERIES


def test_map_const_expr_maps_binary_ref_cast_and_sizeof_nodes() -> None:
    c_int = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    assert map_const_expr(
        CBinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2)),
        type_mapper=MapTypePass(queries=DEFAULT_TARGET_QUERIES),
    ) == MojoBinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2))
    assert map_const_expr(
        CRefExpr(name="VALUE"), type_mapper=MapTypePass(queries=DEFAULT_TARGET_QUERIES)
    ) == MojoRefExpr(name="VALUE")
    assert map_const_expr(
        CCastExpr(target=c_int, expr=IntLiteral(7)),
        type_mapper=MapTypePass(queries=DEFAULT_TARGET_QUERIES),
    ) == MojoCastExpr(target=BuiltinType(MojoBuiltin.C_INT), expr=IntLiteral(7))
    assert map_const_expr(
        CSizeOfExpr(target=c_int), type_mapper=MapTypePass(queries=DEFAULT_TARGET_QUERIES)
    ) == MojoSizeOfExpr(target=BuiltinType(MojoBuiltin.C_INT))


def test_map_const_expr_parses_decimal_and_hex_float_literals() -> None:
    assert map_const_expr(
        CFloatLiteral("1.25f"), type_mapper=MapTypePass(queries=DEFAULT_TARGET_QUERIES)
    ) == MojoFloatLiteral(1.25)
    assert map_const_expr(
        CFloatLiteral("0x1.0p4"), type_mapper=MapTypePass(queries=DEFAULT_TARGET_QUERIES)
    ) == MojoFloatLiteral(16.0)
