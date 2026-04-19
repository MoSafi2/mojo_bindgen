"""ABI-correct resolution of C integer literal suffix families to IR primitives."""

from __future__ import annotations

import clang.cindex as cx

from mojo_bindgen.ir import IntKind, IntType
from mojo_bindgen.parsing.lowering.primitive import (
    PrimitiveResolver,
    default_signed_int_primitive,
)
from mojo_bindgen.utils import build_c_parse_args

_PREWARM_SUFFIXES: frozenset[str] = frozenset(
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

_PROBE_FILENAME = "__bindgen_suffix_probe.c"
_PROBE_DECL_NAME = "__bindgen_m"
_PRIMITIVE_RESOLVER = PrimitiveResolver()


def _integer_spelling_for_suffix(suffix: str) -> str:
    """Return the canonical C integer spelling implied by a literal suffix."""
    if not suffix:
        return "int"

    s = suffix.lower()
    has_unsigned = "u" in s
    long_count = s.count("l")

    if long_count >= 2:
        return "unsigned long long" if has_unsigned else "long long"
    if long_count == 1:
        return "unsigned long" if has_unsigned else "long"
    return "unsigned int" if has_unsigned else "int"


def _parse_args_for_probe(compile_args: list[str]) -> list[str]:
    """Return parse args for a tiny integer-type probe translation unit."""
    return build_c_parse_args(compile_args, default_std="-std=gnu11")


def _probe_source(type_spelling: str) -> str:
    """Return the source text for a tiny variable declaration probe."""
    return f"{type_spelling} {_PROBE_DECL_NAME};\n"


def _fallback_int_type(type_spelling: str) -> IntType:
    """Return a conservative integer fallback if probing fails."""
    prim = default_signed_int_primitive()
    if "unsigned" in type_spelling.split():
        return IntType(
            int_kind=IntKind.UINT,
            size_bytes=prim.size_bytes,
            align_bytes=prim.align_bytes,
        )
    return prim


def _extract_probed_int_type(tu: cx.TranslationUnit) -> IntType | None:
    """Extract the probed integer declaration type from a parsed TU."""
    for cursor in tu.cursor.get_children():
        if cursor.kind == cx.CursorKind.VAR_DECL and cursor.spelling == _PROBE_DECL_NAME:
            scalar = _PRIMITIVE_RESOLVER.resolve_primitive(cursor.type)
            return scalar if isinstance(scalar, IntType) else None
    return None


class LiteralResolver:
    """Resolve integer literal suffix families under a specific compile configuration."""

    def __init__(self, compile_args: list[str], *, prewarm: bool = True) -> None:
        self.compile_args = list(compile_args)
        self._parse_args = _parse_args_for_probe(self.compile_args)
        self._integer_suffix_cache: dict[str, IntType] = {}
        self._type_spelling_int_cache: dict[str, IntType | None] = {}

        if prewarm:
            for suffix in _PREWARM_SUFFIXES:
                self.int_type_for_integer_literal_suffix(suffix)

    def _probe_int_type(self, suffix: str) -> IntType:
        """Probe Clang for the ABI-correct integer type for a suffix family."""
        type_spelling = _integer_spelling_for_suffix(suffix)
        idx = cx.Index.create()
        tu = idx.parse(
            _PROBE_FILENAME,
            args=self._parse_args,
            unsaved_files=[(_PROBE_FILENAME, _probe_source(type_spelling))],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        return _extract_probed_int_type(tu) or _fallback_int_type(type_spelling)

    def int_type_for_integer_literal_suffix(self, suffix: str) -> IntType:
        """Return the ABI-correct integer primitive for a C literal suffix."""
        cached = self._integer_suffix_cache.get(suffix)
        if cached is not None:
            return cached

        prim = self._probe_int_type(suffix)
        self._integer_suffix_cache[suffix] = prim
        return prim

    def int_type_for_type_spelling(self, spelling: str) -> IntType | None:
        """Resolve a C type name (e.g. ``size_t``, ``uint32_t``) to an integer :class:`IntType`, or ``None``."""
        if spelling in self._type_spelling_int_cache:
            return self._type_spelling_int_cache[spelling]

        idx = cx.Index.create()
        tu = idx.parse(
            _PROBE_FILENAME,
            args=self._parse_args,
            unsaved_files=[(_PROBE_FILENAME, _probe_source(spelling))],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        prim = _extract_probed_int_type(tu)
        self._type_spelling_int_cache[spelling] = prim
        return prim
