"""Tests for the extracted parser constant-expression helper."""

from __future__ import annotations

import pytest

from mojo_bindgen.ir import IntLiteral, NullPtrLiteral, RefExpr, StringLiteral
from mojo_bindgen.parsing.const_expr import ConstExprParser
from mojo_bindgen.parsing.lowering import PrimitiveResolver


def _has_libclang() -> bool:
    try:
        import clang.cindex  # noqa: F401
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _has_libclang(),
    reason="libclang not available (use pixi run)",
)


def test_const_expr_parser_parses_supported_leaf_forms() -> None:
    parser = ConstExprParser(PrimitiveResolver([]))

    int_expr = parser.parse_tokens(["42u"])
    null_expr = parser.parse_tokens(["(", "void", "*", ")", "0"])
    string_expr = parser.parse_tokens(['"name"'])
    ref_expr = parser.parse_tokens(["DEFAULT_VALUE"])

    assert isinstance(int_expr.expr, IntLiteral)
    assert int_expr.expr.value == 42
    assert isinstance(null_expr.expr, NullPtrLiteral)
    assert isinstance(string_expr.expr, StringLiteral)
    assert string_expr.expr.value == "name"
    assert isinstance(ref_expr.expr, RefExpr)
    assert ref_expr.expr.name == "DEFAULT_VALUE"


def test_const_expr_parser_rejects_complex_expression_subset() -> None:
    parser = ConstExprParser(PrimitiveResolver([]))
    assert parser.parse_tokens(["1", "+", "2"]) is None
