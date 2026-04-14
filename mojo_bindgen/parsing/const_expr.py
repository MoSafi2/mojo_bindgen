"""Token-based constant-expression parsing for macros and globals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

import clang.cindex as cx

from mojo_bindgen.ir import (
    CharLiteral,
    ConstExpr,
    IntLiteral,
    NullPtrLiteral,
    Primitive,
    PrimitiveKind,
    RefExpr,
    StringLiteral,
)

if TYPE_CHECKING:
    from mojo_bindgen.parsing.lowering import PrimitiveResolver


_INT_LITERAL_RE = re.compile(
    r"^([+-]?)"
    r"(0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)"
    r"([uUlL]*)$",
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
        if len(tokens) == 1:
            raw = tokens[0].strip()
            value, suffix = _match_int_literal(raw)
            if value is not None:
                return ParsedConstExpr(
                    expr=IntLiteral(value),
                    primitive=self.primitive_resolver.primitive_for_integer_literal_suffix(suffix),
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
        if len(tokens) == 2 and tokens[0] == "-":
            value, suffix = _match_int_literal(tokens[1].strip())
            if value is not None:
                return ParsedConstExpr(
                    expr=IntLiteral(-value),
                    primitive=self.primitive_resolver.primitive_for_integer_literal_suffix(suffix),
                )
        if tokens == ["(", "void", "*", ")", "0"] or tokens == ["(", "void", "*", ")", "NULL"]:
            return ParsedConstExpr(
                expr=NullPtrLiteral(),
                primitive=Primitive("void", PrimitiveKind.VOID, False, 0),
            )
        return None
