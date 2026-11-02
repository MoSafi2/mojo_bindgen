"""Unit tests for CIR -> MojoIR constant-expression mapping."""

from __future__ import annotations

import math

import pytest

from mojo_bindgen.ir import (
    BuiltinType,
    ByteOrder,
    CBinaryExpr,
    CCastExpr,
    CFloatLiteral,
    CNullPtrLiteral,
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
    TargetABI,
)
from tests.header_harness import HarnessError, HeaderHarness

DEFAULT_ABI = TargetABI(8, 8, ByteOrder.LITTLE)


def test_map_const_expr_maps_binary_ref_cast_and_sizeof_nodes(bindgen: HeaderHarness) -> None:
    c_int = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    assert bindgen.map_expr(
        CBinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2)),
        target_abi=DEFAULT_ABI,
    ) == MojoBinaryExpr(op="+", lhs=IntLiteral(1), rhs=IntLiteral(2))
    assert bindgen.map_expr(CRefExpr(name="VALUE"), target_abi=DEFAULT_ABI) == MojoRefExpr(
        name="VALUE"
    )
    assert bindgen.map_expr(
        CCastExpr(target=c_int, expr=IntLiteral(7)),
        target_abi=DEFAULT_ABI,
    ) == MojoCastExpr(target=BuiltinType(MojoBuiltin.C_INT), expr=IntLiteral(7))
    assert bindgen.map_expr(CSizeOfExpr(target=c_int), target_abi=DEFAULT_ABI) == IntLiteral(4)


def test_map_const_expr_parses_decimal_and_hex_float_literals(bindgen: HeaderHarness) -> None:
    assert bindgen.map_expr(CFloatLiteral("1.25f"), target_abi=DEFAULT_ABI) == MojoFloatLiteral(
        1.25
    )
    assert bindgen.map_expr(CFloatLiteral("0x1.0p4"), target_abi=DEFAULT_ABI) == MojoFloatLiteral(
        16.0
    )


@pytest.mark.parametrize(
    ("spelling", "value"),
    [
        ("0.0", 0.0),
        ("-0.0", -0.0),
        ("1e-300", 1e-300),
        ("1e300", 1e300),
        ("0x1.8p+2F", 6.0),
        ("0x1p-1022", 2.0**-1022),
    ],
)
def test_map_float_numeric_edges(bindgen: HeaderHarness, spelling: str, value: float) -> None:
    expr = CFloatLiteral(spelling)
    mapped = bindgen.map_expr(expr, target_abi=DEFAULT_ABI)
    assert isinstance(mapped, MojoFloatLiteral)
    assert mapped.value == value
    assert math.copysign(1.0, mapped.value) == math.copysign(1.0, value)
    assert expr.spelling == spelling


def test_expression_mapping_recovers_after_rejected_nullptr(bindgen: HeaderHarness) -> None:
    for _ in range(2):
        with pytest.raises(HarnessError, match="nullptr"):
            bindgen.map_expr(CNullPtrLiteral(), target_abi=DEFAULT_ABI)
        assert bindgen.map_expr(IntLiteral(2**257 + 17), target_abi=DEFAULT_ABI) == IntLiteral(
            2**257 + 17
        )


def test_recursive_expression_mapping_preserves_shared_inputs(bindgen: HeaderHarness) -> None:
    child = CBinaryExpr("+", IntLiteral(2**257), IntLiteral(-7))
    expr = CBinaryExpr("*", child, child)
    expected_child = MojoBinaryExpr("+", IntLiteral(2**257), IntLiteral(-7))
    expected = MojoBinaryExpr("*", expected_child, expected_child)
    for abi in (DEFAULT_ABI, TargetABI(4, 4, ByteOrder.BIG)):
        assert bindgen.map_expr(expr, target_abi=abi) == expected
        assert bindgen.map_expr(expr, target_abi=abi) == expected
    assert expr.lhs is child and expr.rhs is child
    assert child == CBinaryExpr("+", IntLiteral(2**257), IntLiteral(-7))
