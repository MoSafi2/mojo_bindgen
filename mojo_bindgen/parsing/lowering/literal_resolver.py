"""Compile-args-dependent resolution of C literals to IR primitives."""

from __future__ import annotations

import clang.cindex as cx

from mojo_bindgen.ir import IntKind, IntType
from mojo_bindgen.parsing.lowering.primitive import (
    PrimitiveResolver,
    default_signed_int_primitive,
)
from mojo_bindgen.utils import build_c_parse_args

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


def _suffix_probe_parse_args(compile_args: list[str]) -> list[str]:
    """Build parse args for integer literal suffix type probes."""
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


_PRIMITIVE_RESOLVER = PrimitiveResolver()


def _int_primitive_from_clang_type(clang_type: cx.Type) -> IntType:
    scalar = _PRIMITIVE_RESOLVER.resolve_primitive(clang_type)
    if not isinstance(scalar, IntType):
        return default_signed_int_primitive()
    return scalar


class LiteralResolver:
    """Resolve literal-related typing using the same compile flags as the main parse."""

    def __init__(self, compile_args: list[str]) -> None:
        self.compile_args = list(compile_args)
        self._integer_suffix_cache: dict[str, IntType] = {}
        for suffix in _LITERAL_SUFFIX_PREWARM:
            self.int_type_for_integer_literal_suffix(suffix)

    def int_type_for_integer_literal_suffix(self, suffix: str) -> IntType:
        """Map an integer literal suffix to an ABI-correct integer primitive."""
        if suffix in self._integer_suffix_cache:
            return self._integer_suffix_cache[suffix]
        spelling = _c_integer_spelling_for_literal_suffix(suffix)
        idx = cx.Index.create()
        src = f"{spelling} __bindgen_m;\n"
        tu = idx.parse(
            "__bindgen_suffix_probe.c",
            args=_suffix_probe_parse_args(self.compile_args),
            unsaved_files=[("__bindgen_suffix_probe.c", src)],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        prim: IntType | None = None
        for cursor in tu.cursor.get_children():
            if (
                cursor.kind == cx.CursorKind.VAR_DECL
                and cursor.spelling == "__bindgen_m"
            ):
                prim = _int_primitive_from_clang_type(cursor.type)
                break
        if prim is None:
            prim = default_signed_int_primitive()
            if "unsigned" in spelling.split():
                prim = IntType(int_kind=IntKind.UINT, size_bytes=prim.size_bytes)
        self._integer_suffix_cache[suffix] = prim
        return prim
