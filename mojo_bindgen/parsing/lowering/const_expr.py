"""Token-based constant-expression parsing for macros and globals.

This module owns the parser's supported constant-expression subset. It parses
token streams from macros and initializers and relies on ``LiteralResolver``
for literal primitive typing rather than the full lowering pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import clang.cindex as cx

from mojo_bindgen.ir import (
    BinaryExpr,
    CastExpr,
    CharLiteral,
    ConstExpr,
    FloatKind,
    FloatLiteral,
    FloatType,
    IntKind,
    IntLiteral,
    IntType,
    NullPtrLiteral,
    RefExpr,
    StringLiteral,
    UnaryExpr,
    VoidType,
)
from mojo_bindgen.parsing.lowering.literal_resolver import LiteralResolver

_INT_LITERAL_RE = re.compile(
    r"^([+-]?)" r"(0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)" r"([uUlL]*)$",
)

# Single-token type name for the ``(name) -1`` cast idiom (``(size_t)-1``, …).
_CAST_TYPE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_FLOAT_LITERAL_RE = re.compile(
    r"^[+-]?(?:"
    r"(?:[0-9]+\.[0-9]*|\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?"
    r"|"
    r"0[xX](?:[0-9a-fA-F]+\.[0-9a-fA-F]*|\.[0-9a-fA-F]+|[0-9a-fA-F]+)[pP][+-]?[0-9]+"
    r")"
    r"([fFlL]*)$"
)

_PREDEFINED_MACRO_NAMES = {
    "__FILE__",
    "__LINE__",
    "__DATE__",
    "__TIME__",
    "__STDC__",
    "__STDC_VERSION__",
    "__STDC_HOSTED__",
    "__STDC_IEC_559__",
    "__STDC_IEC_559_COMPLEX__",
    "__STDC_ISO_10646__",
    "__STDC_MB_MIGHT_NEQ_WC__",
    "__STDC_ANALYZABLE__",
    "__STDC_LIB_EXT1__",
    "__STDC_ALLOC_LIB__",
    "__COUNTER__",
}


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


def _is_predefined_macro_name(name: str) -> bool:
    """Return whether ``name`` is a standard/compiler predefined macro token."""
    if name in _PREDEFINED_MACRO_NAMES:
        return True
    if name.startswith("__STDC_NO_"):
        return True
    if name.startswith("__STDC_IEC_60559_"):
        return True
    if re.match(r"^__STDC_VERSION_[A-Z0-9_]+_H__$", name):
        return True
    return False


def looks_function_like_macro_body(tokens: list[str]) -> bool:
    """Heuristically detect a function-like macro from raw macro tokens."""
    if not tokens or tokens[0] != "(":
        return False
    depth = 0
    end_index: int | None = None
    for index, tok in enumerate(tokens):
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
            if depth == 0:
                end_index = index
                break
    if end_index is None:
        return False
    inner = tokens[1:end_index]
    if not inner:
        return True
    for tok in inner:
        if tok in {",", "..."}:
            continue
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", tok):
            continue
        return False
    return True


def fold_const_expr(expr: ConstExpr) -> ConstExpr:
    """Constant-fold integer unary/binary expressions where operands are literals."""
    if isinstance(expr, UnaryExpr):
        inner = fold_const_expr(expr.operand)
        if isinstance(inner, IntLiteral):
            v = inner.value
            if expr.op == "-":
                return IntLiteral(-v)
            if expr.op == "~":
                return IntLiteral(~v)
        return UnaryExpr(op=expr.op, operand=inner)
    if isinstance(expr, BinaryExpr):
        lhs = fold_const_expr(expr.lhs)
        rhs = fold_const_expr(expr.rhs)
        if isinstance(lhs, IntLiteral) and isinstance(rhs, IntLiteral):
            a, b = lhs.value, rhs.value
            out = _eval_int_binary(expr.op, a, b)
            if out is not None:
                return IntLiteral(out)
        return BinaryExpr(op=expr.op, lhs=lhs, rhs=rhs)
    if isinstance(expr, CastExpr):
        inner = fold_const_expr(expr.expr)
        return CastExpr(target=expr.target, expr=inner)
    return expr


def _eval_int_binary(op: str, a: int, b: int) -> int | None:
    """Evaluate ``a op b`` for supported integer ops; ``None`` means do not fold."""
    try:
        if op == "|":
            return a | b
        if op == "^":
            return a ^ b
        if op == "&":
            return a & b
        if op == "<<":
            return a << b
        if op == ">>":
            return a >> b
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            if b == 0:
                return None
            # C integer division truncates toward zero
            n = abs(a) // abs(b)
            return n if (a >= 0) == (b >= 0) else -n
        if op == "%":
            if b == 0:
                return None
            return a % b
    except (OverflowError, ValueError):
        return None
    return None


def fold_parsed_const_expr(parsed: ParsedConstExpr) -> ParsedConstExpr:
    """Fold a parsed constant expression, preserving primitive typing when unchanged."""
    folded = fold_const_expr(parsed.expr)
    return ParsedConstExpr(
        expr=folded,
        primitive=parsed.primitive,
        diagnostic=parsed.diagnostic,
    )


@dataclass(frozen=True)
class ParsedConstExpr:
    """A parsed constant expression plus best-effort primitive typing."""

    expr: ConstExpr
    primitive: IntType | FloatType | VoidType | None
    diagnostic: str | None = None


@dataclass(frozen=True)
class ParsedMacro:
    """Classification result for one macro definition."""

    tokens: list[str]
    kind: str
    expr: ConstExpr | None = None
    primitive: IntType | FloatType | VoidType | None = None
    diagnostic: str | None = None


class ConstExprParser:
    """Parse the small constant-expression subset supported by the parser."""

    def __init__(self, literal_resolver: LiteralResolver) -> None:
        self.literal_resolver = literal_resolver

    def parse_macro(
        self,
        cursor: cx.Cursor,
        macro_env: dict[str, list[str]] | None = None,
    ) -> ParsedMacro:
        """Classify a macro definition, preserving unsupported forms.

        When ``macro_env`` is provided (full-TU object-like index), the macro body
        is expanded before parsing so identifiers from included headers fold to
        literals where possible.
        """
        tokens = list(cursor.get_tokens())
        body = [t.spelling for t in tokens[1:]]
        if not body:
            return ParsedMacro(tokens=[], kind="empty", diagnostic="empty macro body")

        if len(body) == 1 and _is_predefined_macro_name(body[0]):
            return ParsedMacro(
                tokens=body,
                kind="predefined",
                diagnostic="predefined macro preserved without evaluation",
            )

        is_function_like = getattr(cursor, "is_macro_function_like", None)
        if (
            (callable(is_function_like) and is_function_like())
            or (
                is_function_like is not None
                and not callable(is_function_like)
                and bool(is_function_like)
            )
            or looks_function_like_macro_body(body)
        ):
            return ParsedMacro(
                tokens=body,
                kind="function_like_unsupported",
                diagnostic="function-like macros are preserved but not parsed",
            )

        expanded = body
        if macro_env is not None:
            from mojo_bindgen.parsing.lowering.macro_env import (
                expand_object_like_macro_tokens,
            )

            expanded = expand_object_like_macro_tokens(body, macro_env)

        parsed = self.parse_tokens(expanded)
        if parsed is None:
            return ParsedMacro(
                tokens=body,
                kind="object_like_unsupported",
                diagnostic="unsupported macro replacement list",
            )
        folded = fold_parsed_const_expr(parsed)
        return ParsedMacro(
            tokens=body,
            kind="object_like_supported",
            expr=folded.expr,
            primitive=folded.primitive,
            diagnostic=folded.diagnostic,
        )

    @staticmethod
    def _looks_function_like_body(tokens: list[str]) -> bool:
        """Heuristically detect a function-like macro from raw macro tokens."""
        return looks_function_like_macro_body(tokens)

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
                primitive=VoidType(),
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
            # C cast: ``(typename) -1`` — not ``(typename) - (1)`` binary minus.
            toks = stream._tokens
            i = stream._index
            if (
                i + 2 < len(toks)
                and _CAST_TYPE_IDENT_RE.match(toks[i] or "")
                and toks[i + 1] == ")"
                and toks[i + 2] in ("-", "+", "~", "(")
            ):
                it = self.literal_resolver.int_type_for_type_spelling(toks[i])
                if it is not None:
                    stream._index = i + 2
                    operand = self._parse_prefix(stream)
                    if operand is not None:
                        return ParsedConstExpr(expr=CastExpr(target=it, expr=operand.expr), primitive=it)
                    stream._index = i
            inner = self._parse_expr(stream, min_prec=0)
            if inner is None or stream.pop() != ")":
                return None
            return inner
        if tok in {"-", "~"}:
            operand = self._parse_prefix(stream)
            if operand is None:
                return None
            return ParsedConstExpr(
                expr=UnaryExpr(op=tok, operand=operand.expr), primitive=operand.primitive
            )
        return self._parse_leaf(tok)

    def _parse_leaf(self, raw: str) -> ParsedConstExpr | None:
        value, suffix = _match_int_literal(raw)
        if value is not None:
            return ParsedConstExpr(
                expr=IntLiteral(value),
                primitive=self.literal_resolver.int_type_for_integer_literal_suffix(suffix),
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
                primitive=IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1),
            )
        if raw.startswith("'") and raw.endswith("'"):
            return ParsedConstExpr(
                expr=CharLiteral(raw[1:-1]),
                primitive=IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1),
            )
        if raw == "NULL":
            return ParsedConstExpr(
                expr=NullPtrLiteral(),
                primitive=VoidType(),
            )
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", raw):
            return ParsedConstExpr(
                expr=RefExpr(raw),
                primitive=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
            )
        return None

    @staticmethod
    def _combine_binary_primitive(
        lhs: IntType | FloatType | VoidType | None,
        rhs: IntType | FloatType | VoidType | None,
    ) -> IntType | FloatType | VoidType | None:
        """Choose a stable best-effort primitive for integer binary expressions."""
        if lhs is None:
            return rhs
        if rhs is None:
            return lhs
        if isinstance(lhs, FloatType) or isinstance(rhs, FloatType):
            return lhs if isinstance(lhs, FloatType) else rhs
        if isinstance(lhs, IntType) and isinstance(rhs, IntType):
            if lhs.size_bytes > rhs.size_bytes:
                return lhs
            if rhs.size_bytes > lhs.size_bytes:
                return rhs
            if lhs.int_kind.name.startswith("U") or not rhs.int_kind.name.startswith("U"):
                return lhs
            return rhs
        return lhs

    @staticmethod
    def _primitive_for_float_literal_suffix(suffix: str) -> FloatType:
        """Choose a best-effort primitive type for a float literal suffix."""
        s = suffix.lower()
        if "f" in s:
            return FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4)
        if "l" in s:
            return FloatType(float_kind=FloatKind.LONG_DOUBLE, size_bytes=16, align_bytes=16)
        return FloatType(float_kind=FloatKind.DOUBLE, size_bytes=8, align_bytes=8)

    @classmethod
    def _is_null_pointer_tokens(cls, tokens: list[str]) -> bool:
        """Return whether the tokens spell a parenthesized ``(void*)0`` null constant."""
        current = tokens[:]
        while True:
            if current == ["(", "void", "*", ")", "0"] or current == [
                "(",
                "void",
                "*",
                ")",
                "NULL",
            ]:
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
    "*": 6,
    "/": 6,
    "%": 6,
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
