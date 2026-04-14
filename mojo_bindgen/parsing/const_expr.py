"""Token-based constant-expression parsing for macros and globals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import clang.cindex as cx

from mojo_bindgen.ir import (
    BinaryExpr,
    CharLiteral,
    ConstExpr,
    FloatLiteral,
    IntLiteral,
    NullPtrLiteral,
    Primitive,
    PrimitiveKind,
    RefExpr,
    StringLiteral,
    UnaryExpr,
)

if TYPE_CHECKING:
    from mojo_bindgen.parsing.lowering import PrimitiveResolver


_INT_LITERAL_RE = re.compile(
    r"^([+-]?)"
    r"(0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)"
    r"([uUlL]*)$",
)

_FLOAT_LITERAL_RE = re.compile(
    r"^[+-]?(?:"
    r"(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?"
    r"|"
    r"0[xX](?:[0-9a-fA-F]+\.[0-9a-fA-F]*|\.[0-9a-fA-F]+|[0-9a-fA-F]+)[pP][+-]?[0-9]+"
    r")"
    r"([fFlL]*)$"
)


def _match_int_literal(raw: str) -> tuple[int | None, str]:
    """Parse a single integer literal token and its suffix."""
    m = _INT_LITERAL_RE.match(raw.strip())
    if not m:
        return None, ""
    sign = m.group(1) or ""
    num_str = m.group(2)
    suffix = m.group(3) or ""
    try:
        value = int(num_str, 0)
    except ValueError:
        return None, ""
    if sign == "-":
        value = -value
    return value, suffix


def _match_float_literal(raw: str) -> tuple[str | None, str]:
    """Parse a float literal token while preserving its original spelling."""
    stripped = raw.strip()
    m = _FLOAT_LITERAL_RE.match(stripped)
    if not m:
        return None, ""
    return stripped, m.group(1) or ""


@dataclass(frozen=True)
class ParsedConstExpr:
    """A parsed constant expression plus best-effort primitive typing."""

    expr: ConstExpr
    primitive: Primitive | None
    diagnostic: str | None = None


class ConstExprParser:
    """Parse the small constant-expression subset supported by the parser."""

    def __init__(self, primitive_resolver: PrimitiveResolver) -> None:
        self.primitive_resolver = primitive_resolver

    def parse_macro(self, cursor: cx.Cursor) -> ParsedConstExpr | None:
        """Parse a macro definition cursor into a supported constant expression."""
        tokens = list(cursor.get_tokens())
        if len(tokens) < 2:
            return None
        return self.parse_tokens([t.spelling for t in tokens[1:]])

    def parse_initializer(self, cursor: cx.Cursor) -> ParsedConstExpr | None:
        """Parse a top-level variable initializer into a supported expression."""
        tokens = list(cursor.get_tokens())
        try:
            eq_i = next(i for i, t in enumerate(tokens) if t.spelling == "=")
        except StopIteration:
            return None
        after_eq = tokens[eq_i + 1 :]
        if after_eq and after_eq[-1].spelling == ";":
            after_eq = after_eq[:-1]
        return self.parse_tokens([t.spelling for t in after_eq])

    def parse_tokens(self, tokens: list[str]) -> ParsedConstExpr | None:
        """Parse a token stream into the supported expression subset."""
        if not tokens:
            return None
        if self._is_null_pointer_tokens(tokens):
            return ParsedConstExpr(
                expr=NullPtrLiteral(),
                primitive=Primitive("void", PrimitiveKind.VOID, False, 0),
            )
        stream = _TokenStream(tokens)
        parsed = self._parse_expr(stream, min_prec=0)
        if parsed is None or stream.peek() is not None:
            return None
        return parsed

    def _parse_expr(self, stream: _TokenStream, min_prec: int) -> ParsedConstExpr | None:
        lhs = self._parse_prefix(stream)
        if lhs is None:
            return None
        while True:
            op = stream.peek()
            if op is None:
                break
            prec = _BINARY_PRECEDENCE.get(op)
            if prec is None or prec < min_prec:
                break
            stream.pop()
            rhs = self._parse_expr(stream, prec + 1)
            if rhs is None:
                return None
            lhs = ParsedConstExpr(
                expr=BinaryExpr(op=op, lhs=lhs.expr, rhs=rhs.expr),
                primitive=self._combine_binary_primitive(lhs.primitive, rhs.primitive),
            )
        return lhs

    def _parse_prefix(self, stream: _TokenStream) -> ParsedConstExpr | None:
        tok = stream.pop()
        if tok is None:
            return None
        if tok == "(":
            inner = self._parse_expr(stream, min_prec=0)
            if inner is None or stream.pop() != ")":
                return None
            return inner
        if tok in {"-", "~"}:
            operand = self._parse_prefix(stream)
            if operand is None:
                return None
            return ParsedConstExpr(expr=UnaryExpr(op=tok, operand=operand.expr), primitive=operand.primitive)
        return self._parse_leaf(tok)

    def _parse_leaf(self, raw: str) -> ParsedConstExpr | None:
        value, suffix = _match_int_literal(raw)
        if value is not None:
            return ParsedConstExpr(
                expr=IntLiteral(value),
                primitive=self.primitive_resolver.primitive_for_integer_literal_suffix(suffix),
            )
        float_value, float_suffix = _match_float_literal(raw)
        if float_value is not None:
            return ParsedConstExpr(
                expr=FloatLiteral(float_value),
                primitive=self._primitive_for_float_literal_suffix(float_suffix),
            )
        if raw.startswith('"') and raw.endswith('"'):
            return ParsedConstExpr(
                expr=StringLiteral(raw[1:-1]),
                primitive=Primitive("char", PrimitiveKind.CHAR, True, 1),
            )
        if raw.startswith("'") and raw.endswith("'"):
            return ParsedConstExpr(
                expr=CharLiteral(raw[1:-1]),
                primitive=Primitive("char", PrimitiveKind.CHAR, True, 1),
            )
        if raw == "NULL":
            return ParsedConstExpr(
                expr=NullPtrLiteral(),
                primitive=Primitive("void", PrimitiveKind.VOID, False, 0),
            )
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", raw):
            return ParsedConstExpr(
                expr=RefExpr(raw),
                primitive=Primitive("int", PrimitiveKind.INT, True, 4),
            )
        return None

    @staticmethod
    def _combine_binary_primitive(lhs: Primitive | None, rhs: Primitive | None) -> Primitive | None:
        """Choose a stable best-effort primitive for integer binary expressions."""
        if lhs is None:
            return rhs
        if rhs is None:
            return lhs
        if lhs.kind == PrimitiveKind.FLOAT or rhs.kind == PrimitiveKind.FLOAT:
            return lhs if lhs.kind == PrimitiveKind.FLOAT else rhs
        if lhs.kind == PrimitiveKind.INT and rhs.kind == PrimitiveKind.INT:
            if lhs.size_bytes > rhs.size_bytes:
                return lhs
            if rhs.size_bytes > lhs.size_bytes:
                return rhs
            if not lhs.is_signed or rhs.is_signed:
                return lhs
            return rhs
        return lhs

    @staticmethod
    def _primitive_for_float_literal_suffix(suffix: str) -> Primitive:
        """Choose a best-effort primitive type for a float literal suffix."""
        s = suffix.lower()
        if "f" in s:
            return Primitive("float", PrimitiveKind.FLOAT, False, 4)
        if "l" in s:
            return Primitive("long double", PrimitiveKind.FLOAT, False, 16)
        return Primitive("double", PrimitiveKind.FLOAT, False, 8)

    @classmethod
    def _is_null_pointer_tokens(cls, tokens: list[str]) -> bool:
        """Return whether the tokens spell a parenthesized ``(void*)0`` null constant."""
        current = tokens[:]
        while True:
            if current == ["(", "void", "*", ")", "0"] or current == ["(", "void", "*", ")", "NULL"]:
                return True
            stripped = cls._strip_outer_parens(current)
            if stripped == current:
                return False
            current = stripped

    @staticmethod
    def _strip_outer_parens(tokens: list[str]) -> list[str]:
        """Strip one balanced outer parenthesis layer when present."""
        if len(tokens) < 2 or tokens[0] != "(" or tokens[-1] != ")":
            return tokens
        depth = 0
        for index, tok in enumerate(tokens):
            if tok == "(":
                depth += 1
            elif tok == ")":
                depth -= 1
            if depth == 0 and index != len(tokens) - 1:
                return tokens
        return tokens[1:-1]


_BINARY_PRECEDENCE = {
    "|": 1,
    "^": 2,
    "&": 3,
    "<<": 4,
    ">>": 4,
    "+": 5,
    "-": 5,
}


class _TokenStream:
    """Small mutable token stream for expression parsing."""

    def __init__(self, tokens: list[str]) -> None:
        self._tokens = tokens
        self._index = 0

    def peek(self) -> str | None:
        if self._index >= len(self._tokens):
            return None
        return self._tokens[self._index]

    def pop(self) -> str | None:
        tok = self.peek()
        if tok is not None:
            self._index += 1
        return tok
