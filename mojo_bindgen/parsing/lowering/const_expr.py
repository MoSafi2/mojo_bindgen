"""Token-based constant-expression parsing for macros and globals.

This module owns the parser's supported constant-expression subset. It parses
token streams from macros and initializers and relies on ``LiteralResolver``
for literal primitive typing rather than the full lowering pipeline.
"""

from __future__ import annotations

import re
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

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
    MacroDeclKind,
    NullPtrLiteral,
    RefExpr,
    SizeOfExpr,
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

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


def _int_primitive(
    literal_resolver: LiteralResolver,
    suffix: str,
) -> IntType:
    if suffix:
        return literal_resolver.int_type_for_integer_literal_suffix(suffix)
    return literal_resolver.int_type_for_integer_literal_suffix("")


def _clone_parsed_const_expr(parsed: ParsedConstExpr) -> ParsedConstExpr:
    return ParsedConstExpr(
        expr=parsed.expr,
        primitive=parsed.primitive,
        diagnostic=parsed.diagnostic,
    )


def _decode_c_escapes(raw: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch != "\\" or i + 1 >= len(raw):
            out.append(ch)
            i += 1
            continue
        i += 1
        esc = raw[i]
        simple = {
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "v": "\v",
            "\\": "\\",
            "'": "'",
            '"': '"',
            "?": "?",
        }
        if esc in simple:
            out.append(simple[esc])
            i += 1
            continue
        if esc in "01234567":
            start = i
            i += 1
            while i < len(raw) and i - start < 3 and raw[i] in "01234567":
                i += 1
            out.append(chr(int(raw[start:i], 8)))
            continue
        if esc == "x":
            i += 1
            start = i
            while i < len(raw) and raw[i] in "0123456789abcdefABCDEF":
                i += 1
            out.append(chr(int(raw[start:i], 16)) if i > start else "\\x")
            continue
        out.append(esc)
        i += 1
    return "".join(out)


def _string_token_value(raw: str) -> str | None:
    if raw.startswith('"') and raw.endswith('"'):
        return _decode_c_escapes(raw[1:-1])
    return None


def fold_const_expr(expr: ConstExpr) -> ConstExpr:
    """Constant-fold integer unary/binary expressions where operands are literals."""
    if isinstance(expr, UnaryExpr):
        inner = fold_const_expr(expr.operand)
        if isinstance(inner, IntLiteral):
            v = inner.value
            if expr.op == "+":
                return IntLiteral(v)
            if expr.op == "-":
                return IntLiteral(-v)
            if expr.op == "~":
                return IntLiteral(~v)
            if expr.op == "!":
                return IntLiteral(0 if v else 1)
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
        if op == "<":
            return int(a < b)
        if op == "<=":
            return int(a <= b)
        if op == ">":
            return int(a > b)
        if op == ">=":
            return int(a >= b)
        if op == "==":
            return int(a == b)
        if op == "!=":
            return int(a != b)
        if op == "&&":
            return int(bool(a) and bool(b))
        if op == "||":
            return int(bool(a) or bool(b))
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


def const_expr_needs_clang_macro_fallback(expr: ConstExpr) -> bool:
    """Return whether a parsed macro expression is structurally risky to emit."""
    if isinstance(expr, RefExpr):
        return True
    if isinstance(expr, UnaryExpr):
        return expr.op == "!" or const_expr_needs_clang_macro_fallback(expr.operand)
    if isinstance(expr, BinaryExpr):
        return (
            expr.op in {"&&", "||"}
            or const_expr_needs_clang_macro_fallback(expr.lhs)
            or const_expr_needs_clang_macro_fallback(expr.rhs)
        )
    if isinstance(expr, CastExpr):
        return const_expr_needs_clang_macro_fallback(expr.expr)
    return False


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
    kind: MacroDeclKind
    expr: ConstExpr | None = None
    primitive: IntType | FloatType | VoidType | None = None
    diagnostic: str | None = None


class ConstExprParser:
    """Parse the small constant-expression subset supported by the parser."""

    def __init__(
        self,
        literal_resolver: LiteralResolver,
        *,
        macro_values: Mapping[str, ParsedConstExpr] | None = None,
        macro_defaults: bool = False,
    ) -> None:
        self.literal_resolver = literal_resolver
        self.macro_values = macro_values
        self.macro_defaults = macro_defaults

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
        tokens = _merge_adjacent_string_literals(tokens)
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
            if op == "?" and min_prec <= 0:
                stream.pop()
                truthy = self._parse_expr(stream, min_prec=0)
                if truthy is None or stream.pop() != ":":
                    return None
                falsy = self._parse_expr(stream, min_prec=0)
                if falsy is None:
                    return None
                condition = fold_const_expr(lhs.expr)
                if not isinstance(condition, IntLiteral):
                    return None
                lhs = truthy if condition.value != 0 else falsy
                continue
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
        if tok == "sizeof":
            sizeof_expr = self._parse_sizeof_expr(stream)
            if sizeof_expr is not None:
                return sizeof_expr
            return None
        if tok == "(":
            # C cast: ``(typename) -1`` — not ``(typename) - (1)`` binary minus.
            toks = stream._tokens
            i = stream._index
            if (
                i + 2 < len(toks)
                and _CAST_TYPE_IDENT_RE.match(toks[i] or "")
                and toks[i + 1] == ")"
                and toks[i + 2] in ("-", "+", "~", "!", "(")
            ):
                it = self.literal_resolver.int_type_for_type_spelling(toks[i])
                if it is not None:
                    stream._index = i + 2
                    operand = self._parse_prefix(stream)
                    if operand is not None:
                        return ParsedConstExpr(
                            expr=CastExpr(target=it, expr=operand.expr), primitive=it
                        )
                    stream._index = i
            inner = self._parse_expr(stream, min_prec=0)
            if inner is None or stream.pop() != ")":
                return None
            return inner
        if tok in {"+", "-", "~", "!"}:
            direct_unsuffixed_int = False
            if tok == "-":
                next_tok = stream.peek()
                if next_tok is not None:
                    value, suffix = _match_int_literal(next_tok)
                    direct_unsuffixed_int = value is not None and suffix == ""
            operand = self._parse_prefix(stream)
            if operand is None:
                return None
            primitive = operand.primitive
            if (
                tok == "-"
                and direct_unsuffixed_int
                and isinstance(operand.expr, IntLiteral)
                and self.macro_defaults
            ):
                primitive = self.literal_resolver.int_type_for_integer_literal_suffix("")
            return ParsedConstExpr(
                expr=UnaryExpr(op=tok, operand=operand.expr), primitive=primitive
            )
        return self._parse_leaf(tok)

    def _parse_sizeof_expr(self, stream: _TokenStream) -> ParsedConstExpr | None:
        """Parse a ``sizeof(type)`` token sequence into a :class:`SizeOfExpr`."""
        start = stream._index
        if stream.pop() != "(":
            return None
        depth = 1
        inner: list[str] = []
        while True:
            tok = stream.pop()
            if tok is None:
                stream._index = start
                return None
            if tok == "(":
                depth += 1
            elif tok == ")":
                depth -= 1
                if depth == 0:
                    break
            if depth > 0:
                inner.append(tok)
        type_spelling = " ".join(inner).strip()
        if not type_spelling:
            stream._index = start
            return None
        size_type = self.literal_resolver.int_type_for_type_spelling(type_spelling)
        if size_type is None:
            stream._index = start
            return None
        return ParsedConstExpr(
            expr=SizeOfExpr(target=size_type),
            primitive=size_type,
        )

    def _parse_leaf(self, raw: str) -> ParsedConstExpr | None:
        value, suffix = _match_int_literal(raw)
        if value is not None:
            return ParsedConstExpr(
                expr=IntLiteral(value),
                primitive=_int_primitive(
                    self.literal_resolver,
                    suffix,
                ),
            )
        float_value, float_suffix = _match_float_literal(raw)
        if float_value is not None:
            return ParsedConstExpr(
                expr=FloatLiteral(float_value),
                primitive=self._primitive_for_float_literal_suffix(float_suffix),
            )
        string_value = _string_token_value(raw)
        if string_value is not None:
            return ParsedConstExpr(
                expr=StringLiteral(string_value),
                primitive=IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1),
            )
        if raw.startswith("'") and raw.endswith("'"):
            return ParsedConstExpr(
                expr=CharLiteral(_decode_c_escapes(raw[1:-1])),
                primitive=IntType(int_kind=IntKind.CHAR_S, size_bytes=1, align_bytes=1),
            )
        if raw == "NULL":
            return ParsedConstExpr(
                expr=NullPtrLiteral(),
                primitive=VoidType(),
            )
        if _IDENT_RE.match(raw):
            if self.macro_values is not None and raw in self.macro_values:
                return _clone_parsed_const_expr(self.macro_values[raw])
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
    "||": 1,
    "&&": 2,
    "|": 3,
    "^": 4,
    "&": 5,
    "==": 6,
    "!=": 6,
    "<": 7,
    "<=": 7,
    ">": 7,
    ">=": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "%": 10,
}


def _merge_adjacent_string_literals(tokens: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(tokens):
        value = _string_token_value(tokens[i])
        if value is None:
            out.append(tokens[i])
            i += 1
            continue
        parts = [value]
        i += 1
        while i < len(tokens):
            next_value = _string_token_value(tokens[i])
            if next_value is None:
                break
            parts.append(next_value)
            i += 1
        merged = "".join(parts).replace("\\", "\\\\").replace('"', '\\"')
        out.append(f'"{merged}"')
    return out


class ClangMacroFallback:
    """Opt-in integer fallback for macro expressions unsupported by the local parser."""

    _PROBE_ENUM = "__mojo_bindgen_macro_value"
    _PROBE_FILE = "__mojo_bindgen_macro_fallback.c"

    def __init__(
        self,
        *,
        headers: list[Path],
        compile_args: list[str],
        build_dir: Path | None = None,
    ) -> None:
        self.headers = headers
        self.compile_args = compile_args
        self.build_dir = build_dir

    def evaluate_integer(self, macro_name: str) -> int | None:
        filename = self._probe_filename()
        source = self._source(macro_name)
        idx = cx.Index.create()
        try:
            tu = idx.parse(
                filename,
                args=self.compile_args,
                unsaved_files=[(filename, source)],
                options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
            )
        except cx.TranslationUnitLoadError:
            return None
        for cursor in tu.cursor.walk_preorder():
            if (
                cursor.kind == cx.CursorKind.ENUM_CONSTANT_DECL
                and cursor.spelling == self._PROBE_ENUM
            ):
                return cursor.enum_value
        return None

    def _probe_filename(self) -> str:
        if self.build_dir is None:
            return self._PROBE_FILE
        self.build_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix="macro_fallback_",
            suffix=".c",
            dir=self.build_dir,
            delete=True,
        ) as f:
            return f.name

    def _source(self, macro_name: str) -> str:
        includes = "\n".join(f'#include "{_c_string(str(header))}"' for header in self.headers)
        return f"{includes}\nenum {{ {self._PROBE_ENUM} = ({macro_name}) }};\n"


def _c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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
