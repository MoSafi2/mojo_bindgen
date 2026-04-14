"""Primitive classification and literal ABI probing for parser lowering.

This module owns primitive-type semantics used by type lowering and
constant-expression parsing. It does not lower declarations or records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import clang.cindex as cx

from mojo_bindgen.ir import Primitive, PrimitiveKind
from mojo_bindgen.utils import build_c_parse_args


@dataclass(frozen=True)
class BuiltinPrimitiveSpelling:
    """Kind metadata for canonical primitive C spellings."""

    kind: PrimitiveKind
    is_signed: bool = False


_PS_VOID = BuiltinPrimitiveSpelling(kind=PrimitiveKind.VOID)
_PS_BOOL = BuiltinPrimitiveSpelling(kind=PrimitiveKind.BOOL)
_PS_CHAR = BuiltinPrimitiveSpelling(kind=PrimitiveKind.CHAR)
_PS_SINT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.INT, is_signed=True)
_PS_UINT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.INT, is_signed=False)
_PS_FLOAT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.FLOAT)

_PRIMITIVE_SPELLINGS: dict[str, BuiltinPrimitiveSpelling] = {
    "void": _PS_VOID,
    "_Bool": _PS_BOOL,
    "char": _PS_CHAR,
    "signed char": _PS_SINT,
    "unsigned char": _PS_UINT,
    "short": _PS_SINT,
    "short int": _PS_SINT,
    "signed short": _PS_SINT,
    "signed short int": _PS_SINT,
    "unsigned short": _PS_UINT,
    "unsigned short int": _PS_UINT,
    "int": _PS_SINT,
    "signed": _PS_SINT,
    "signed int": _PS_SINT,
    "unsigned": _PS_UINT,
    "unsigned int": _PS_UINT,
    "long": _PS_SINT,
    "long int": _PS_SINT,
    "signed long": _PS_SINT,
    "unsigned long": _PS_UINT,
    "unsigned long int": _PS_UINT,
    "long long": _PS_SINT,
    "long long int": _PS_SINT,
    "signed long long": _PS_SINT,
    "signed long long int": _PS_SINT,
    "unsigned long long": _PS_UINT,
    "unsigned long long int": _PS_UINT,
    "float": _PS_FLOAT,
    "double": _PS_FLOAT,
    "long double": _PS_FLOAT,
    "int8_t": _PS_SINT,
    "int16_t": _PS_SINT,
    "int32_t": _PS_SINT,
    "int64_t": _PS_SINT,
    "uint8_t": _PS_UINT,
    "uint16_t": _PS_UINT,
    "uint32_t": _PS_UINT,
    "uint64_t": _PS_UINT,
    "size_t": _PS_UINT,
    "ssize_t": _PS_SINT,
    "ptrdiff_t": _PS_SINT,
    "intptr_t": _PS_SINT,
    "uintptr_t": _PS_UINT,
}


def default_signed_int_primitive() -> Primitive:
    """Return the parser's default signed int primitive fallback."""
    return Primitive("int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)


def _c_integer_spelling_for_literal_suffix(suffix: str) -> str:
    """Map a C integer literal suffix to a canonical integer spelling."""
    if not suffix:
        return "int"
    s = suffix.lower()
    has_u = "u" in s
    l_count = s.count("l")
    if l_count >= 2:
        return "unsigned long long" if has_u else "long long"
    if l_count == 1:
        return "unsigned long" if has_u else "long"
    return "unsigned int" if has_u else "int"


_LITERAL_SUFFIX_PREWARM: frozenset[str] = frozenset(
    {
        "",
        "u",
        "U",
        "l",
        "L",
        "ll",
        "LL",
        "ul",
        "uL",
        "Ul",
        "UL",
        "lu",
        "lU",
        "Lu",
        "LU",
        "llu",
        "llU",
        "LLu",
        "LLU",
        "ull",
        "uLL",
        "Ull",
        "ULL",
    }
)


def _suffix_probe_parse_args(compile_args: list[str]) -> list[str]:
    """Build parse args for integer literal suffix type probes."""
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


class PrimitiveResolver:
    """Primitive classification and integer-literal ABI probing."""

    def __init__(self, compile_args: list[str]) -> None:
        self.compile_args = list(compile_args)
        self._literal_suffix_cache: dict[str, Primitive] = {}
        for suffix in _LITERAL_SUFFIX_PREWARM:
            self.primitive_for_integer_literal_suffix(suffix)

    def primitive_for_integer_literal_suffix(self, suffix: str) -> Primitive:
        """Map an integer literal suffix to an ABI-correct primitive."""
        if suffix in self._literal_suffix_cache:
            return self._literal_suffix_cache[suffix]
        spelling = _c_integer_spelling_for_literal_suffix(suffix)
        idx = cx.Index.create()
        src = f"{spelling} __bindgen_m;\n"
        tu = idx.parse(
            "__bindgen_suffix_probe.c",
            args=_suffix_probe_parse_args(self.compile_args),
            unsaved_files=[("__bindgen_suffix_probe.c", src)],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        prim: Primitive | None = None
        for cursor in tu.cursor.get_children():
            if cursor.kind == cx.CursorKind.VAR_DECL and cursor.spelling == "__bindgen_m":
                prim = self.make_primitive_from_kind(cursor.type)
                break
        if prim is None:
            prim = default_signed_int_primitive()
            prim.name = spelling
            prim.is_signed = "unsigned" not in spelling.split()
        self._literal_suffix_cache[suffix] = prim
        return prim

    def make_primitive_from_kind(self, clang_type: cx.Type) -> Primitive:
        """Lower a scalar clang type to a primitive IR node."""
        canonical = clang_type.get_canonical()
        spelling = canonical.spelling
        norm = re.sub(r"\b(const|volatile|restrict)\b", "", spelling).strip()

        defaults = _PRIMITIVE_SPELLINGS.get(norm)
        if defaults:
            kind = defaults.kind
            if kind == PrimitiveKind.INT:
                is_signed = defaults.is_signed
            elif kind == PrimitiveKind.CHAR:
                is_signed = canonical.kind == cx.TypeKind.CHAR_S
            else:
                is_signed = False
        else:
            tk = canonical.kind
            if tk == cx.TypeKind.BOOL:
                kind = PrimitiveKind.BOOL
                is_signed = False
            elif tk in (
                cx.TypeKind.FLOAT,
                cx.TypeKind.DOUBLE,
                cx.TypeKind.LONGDOUBLE,
                cx.TypeKind.HALF,
            ):
                kind = PrimitiveKind.FLOAT
                is_signed = False
            elif tk in (cx.TypeKind.CHAR_S, cx.TypeKind.CHAR_U) and norm == "char":
                kind = PrimitiveKind.CHAR
                is_signed = tk == cx.TypeKind.CHAR_S
            else:
                kind = PrimitiveKind.INT
                is_signed = tk in (
                    cx.TypeKind.CHAR_S,
                    cx.TypeKind.SCHAR,
                    cx.TypeKind.SHORT,
                    cx.TypeKind.INT,
                    cx.TypeKind.LONG,
                    cx.TypeKind.LONGLONG,
                    cx.TypeKind.INT128,
                    cx.TypeKind.WCHAR,
                )

        size_raw = canonical.get_size()
        size_bytes = size_raw if size_raw > 0 else 0
        return Primitive(
            name=norm or spelling,
            kind=kind,
            is_signed=is_signed,
            size_bytes=size_bytes,
        )

    def resolve_primitive(self, clang_type: cx.Type) -> Primitive | None:
        """Return a primitive for scalar clang types, else ``None``."""
        canonical = clang_type.get_canonical()
        tk = canonical.kind
        scalar_kinds = {
            cx.TypeKind.BOOL,
            cx.TypeKind.CHAR_U,
            cx.TypeKind.UCHAR,
            cx.TypeKind.CHAR16,
            cx.TypeKind.CHAR32,
            cx.TypeKind.USHORT,
            cx.TypeKind.UINT,
            cx.TypeKind.ULONG,
            cx.TypeKind.ULONGLONG,
            cx.TypeKind.UINT128,
            cx.TypeKind.CHAR_S,
            cx.TypeKind.SCHAR,
            cx.TypeKind.WCHAR,
            cx.TypeKind.SHORT,
            cx.TypeKind.INT,
            cx.TypeKind.LONG,
            cx.TypeKind.LONGLONG,
            cx.TypeKind.INT128,
            cx.TypeKind.FLOAT,
            cx.TypeKind.DOUBLE,
            cx.TypeKind.LONGDOUBLE,
            cx.TypeKind.HALF,
        }
        if tk not in scalar_kinds:
            return None
        return self.make_primitive_from_kind(clang_type)
