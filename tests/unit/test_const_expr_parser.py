"""Tests for the extracted parser constant-expression helper."""

from __future__ import annotations

import pytest

from mojo_bindgen.ir import BinaryExpr, FloatLiteral, FloatType, IntLiteral, IntType, NullPtrLiteral, RefExpr, StringLiteral
from mojo_bindgen.parsing.lowering import ConstExprParser, PrimitiveResolver


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
    float_expr = parser.parse_tokens(["3.14159265"])
    null_expr = parser.parse_tokens(["(", "void", "*", ")", "0"])
    nested_null_expr = parser.parse_tokens(["(", "(", "void", "*", ")", "0", ")"])
    string_expr = parser.parse_tokens(['"name"'])
    ref_expr = parser.parse_tokens(["DEFAULT_VALUE"])
    combined_expr = parser.parse_tokens(["(", "0x1u", "|", "0x2u", ")"])

    assert isinstance(int_expr.expr, IntLiteral)
    assert int_expr.expr.value == 42
    assert isinstance(float_expr.expr, FloatLiteral)
    assert float_expr.expr.value == "3.14159265"
    assert isinstance(float_expr.primitive, FloatType)
    assert float_expr.primitive.float_kind.value == "DOUBLE"
    assert isinstance(null_expr.expr, NullPtrLiteral)
    assert isinstance(nested_null_expr.expr, NullPtrLiteral)
    assert isinstance(string_expr.expr, StringLiteral)
    assert string_expr.expr.value == "name"
    assert isinstance(ref_expr.expr, RefExpr)
    assert ref_expr.expr.name == "DEFAULT_VALUE"
    assert isinstance(combined_expr.expr, BinaryExpr)
    assert combined_expr.expr.op == "|"
    assert isinstance(combined_expr.primitive, IntType)
    assert combined_expr.primitive.int_kind.value == "UINT"


def test_const_expr_parser_rejects_still_unsupported_expression_subset() -> None:
    parser = ConstExprParser(PrimitiveResolver([]))
    assert parser.parse_tokens(["sizeof", "(", "int", ")"]) is None


def test_const_expr_parser_classifies_broader_predefined_and_function_like_macros() -> None:
    parser = ConstExprParser(PrimitiveResolver([]))

    class _Token:
        def __init__(self, spelling: str) -> None:
            self.spelling = spelling

    class _Cursor:
        def __init__(self, spelling: str, body: list[str], *, function_like: bool = False) -> None:
            self.spelling = spelling
            self._tokens = [_Token(spelling), *[_Token(tok) for tok in body]]
            self._function_like = function_like

        def get_tokens(self) -> list[_Token]:
            return self._tokens

        def is_macro_function_like(self) -> bool:
            return self._function_like

    predefined = parser.parse_macro(_Cursor("MACRO_FILE", ["__FILE__"]))
    stdc_version = parser.parse_macro(_Cursor("MACRO_STDC_VERSION", ["__STDC_VERSION__"]))
    stdc_no_atomics = parser.parse_macro(_Cursor("MACRO_STDC_NO_ATOMICS", ["__STDC_NO_ATOMICS__"]))
    header_version = parser.parse_macro(_Cursor("MACRO_STDIO_VERSION", ["__STDC_VERSION_STDIO_H__"]))
    function_like = parser.parse_macro(_Cursor("MACRO_FUNC", ["x", "(", "x", ")", "+", "1"], function_like=True))

    assert predefined.kind == "predefined"
    assert predefined.tokens == ["__FILE__"]
    assert predefined.expr is None
    assert stdc_version.kind == "predefined"
    assert stdc_version.tokens == ["__STDC_VERSION__"]
    assert stdc_no_atomics.kind == "predefined"
    assert stdc_no_atomics.tokens == ["__STDC_NO_ATOMICS__"]
    assert header_version.kind == "predefined"
    assert header_version.tokens == ["__STDC_VERSION_STDIO_H__"]
    assert function_like.kind == "function_like_unsupported"
    assert function_like.expr is None
