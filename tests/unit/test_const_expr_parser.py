"""Tests for the extracted parser constant-expression helper."""

from __future__ import annotations

import pytest

from mojo_bindgen.ir import (
    BinaryExpr,
    CastExpr,
    CharLiteral,
    FloatLiteral,
    FloatType,
    IntLiteral,
    IntType,
    NullPtrLiteral,
    RefExpr,
    SizeOfExpr,
    StringLiteral,
)
from mojo_bindgen.parsing.lowering import ConstExprParser, LiteralResolver
from mojo_bindgen.parsing.lowering.const_expr import fold_const_expr, fold_parsed_const_expr


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
    parser = ConstExprParser(LiteralResolver([]))

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


def test_const_expr_parser_types_unsuffixed_negative_macro_literals_as_signed() -> None:
    parser = ConstExprParser(LiteralResolver([]), macro_defaults=True)

    positive = parser.parse_tokens(["1"])
    assert positive is not None
    assert isinstance(positive.primitive, IntType)
    assert positive.primitive.int_kind.value == "INT"

    out = parser.parse_tokens(["-", "1"])
    assert out is not None
    assert isinstance(out.primitive, IntType)
    assert out.primitive.int_kind.value == "INT"

    folded = fold_parsed_const_expr(out)
    assert isinstance(folded.expr, IntLiteral)
    assert folded.expr.value == -1
    assert isinstance(folded.primitive, IntType)
    assert folded.primitive.int_kind.value == "INT"


def test_const_expr_parser_preserves_explicit_unsigned_macro_literal_type() -> None:
    parser = ConstExprParser(LiteralResolver([]), macro_defaults=True)

    out = parser.parse_tokens(["-", "1u"])
    assert out is not None
    assert isinstance(out.primitive, IntType)
    assert out.primitive.int_kind.value == "UINT"

    folded = fold_parsed_const_expr(out)
    assert isinstance(folded.expr, IntLiteral)
    assert folded.expr.value == -1
    assert isinstance(folded.primitive, IntType)
    assert folded.primitive.int_kind.value == "UINT"


def test_const_expr_parser_preserves_clang_resolved_cast_integer_type() -> None:
    parser = ConstExprParser(LiteralResolver([]), macro_defaults=True)

    out = parser.parse_tokens(["(", "__SIZE_TYPE__", ")", "-", "1"])
    assert out is not None
    assert isinstance(out.expr, CastExpr)
    assert isinstance(out.primitive, IntType)
    assert out.primitive.int_kind.name.startswith("U")


def test_const_expr_parser_cast_size_t_minus_one() -> None:
    """``(size_t)-1`` is a cast of ``-1``, not ``size_t`` minus ``1`` (see ``CURL_ZERO_TERMINATED``)."""
    parser = ConstExprParser(LiteralResolver([]))
    out = parser.parse_tokens(["(", "(", "size_t", ")", "-", "1", ")"])
    assert out is not None
    assert isinstance(out.expr, CastExpr)
    assert isinstance(out.expr.target, IntType)
    folded = fold_const_expr(out.expr)
    assert isinstance(folded, CastExpr)
    assert isinstance(folded.expr, IntLiteral)
    assert folded.expr.value == -1


def test_const_expr_parser_parses_sizeof_type_expressions() -> None:
    parser = ConstExprParser(LiteralResolver([]))
    out = parser.parse_tokens(["sizeof", "(", "int", ")"])
    assert out is not None
    assert isinstance(out.expr, SizeOfExpr)
    assert isinstance(out.expr.target, IntType)


def test_const_expr_parser_folds_logical_comparison_and_ternary_ops() -> None:
    parser = ConstExprParser(LiteralResolver([]))

    logical = parser.parse_tokens(["!", "0", "&&", "(", "4", ">=", "3", ")"])
    ternary = parser.parse_tokens(["(", "1", "<", "2", ")", "?", "40", "+", "2", ":", "0"])

    assert logical is not None
    logical_folded = fold_const_expr(logical.expr)
    assert isinstance(logical_folded, IntLiteral)
    assert logical_folded.value == 1

    assert ternary is not None
    ternary_folded = fold_const_expr(ternary.expr)
    assert isinstance(ternary_folded, IntLiteral)
    assert ternary_folded.value == 42


def test_const_expr_parser_decodes_string_concat_and_char_escapes() -> None:
    parser = ConstExprParser(LiteralResolver([]))

    string_expr = parser.parse_tokens(['"a\\n"', '"b"'])
    char_expr = parser.parse_tokens(["'\\x41'"])

    assert string_expr is not None
    assert isinstance(string_expr.expr, StringLiteral)
    assert string_expr.expr.value == "a\nb"
    assert char_expr is not None
    assert isinstance(char_expr.expr, CharLiteral)
    assert char_expr.expr.value == "A"


def test_const_expr_parser_resolves_nested_macro_values() -> None:
    parser_value = ConstExprParser(LiteralResolver([])).parse_tokens(["40"])
    assert parser_value is not None
    values = {"A": parser_value}
    parser = ConstExprParser(LiteralResolver([]), macro_values=values)

    out = parser.parse_tokens(["A", "+", "2"])
    assert out is not None
    folded = fold_const_expr(out.expr)
    assert isinstance(folded, IntLiteral)
    assert folded.value == 42


def test_const_expr_parser_classifies_broader_predefined_and_function_like_macros() -> None:
    parser = ConstExprParser(LiteralResolver([]))

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
    header_version = parser.parse_macro(
        _Cursor("MACRO_STDIO_VERSION", ["__STDC_VERSION_STDIO_H__"])
    )
    function_like = parser.parse_macro(
        _Cursor("MACRO_FUNC", ["x", "(", "x", ")", "+", "1"], function_like=True)
    )

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
