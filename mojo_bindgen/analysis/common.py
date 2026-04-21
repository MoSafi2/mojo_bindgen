"""Shared helpers for Mojo analysis modules."""

from __future__ import annotations

import ctypes

from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.ir import Field, FloatType, IntType, VoidType

_MOJO_MAX_ALIGN_BYTES = 1 << 29
_POINTER_SIZE_BYTES = ctypes.sizeof(ctypes.c_void_p)
_POINTER_ALIGN_BYTES = ctypes.alignment(ctypes.c_void_p)


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def mojo_align_decorator_ok(align_bytes: int) -> bool:
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)


def scalar_comment_name(t: IntType | FloatType | VoidType) -> str:
    if isinstance(t, IntType):
        return t.int_kind.value
    if isinstance(t, FloatType):
        return t.float_kind.value
    return "VOID"


def mojo_float_literal_text(c_spelling: str) -> str:
    text = c_spelling.rstrip()
    while text and text[-1] in "fFlL":
        text = text[:-1]
    return text


def field_mojo_name(field: Field, index: int) -> str:
    if field.source_name:
        return mojo_ident(field.source_name)
    if field.name:
        return mojo_ident(field.name)
    return f"_anon_{index}"


__all__ = [
    "_POINTER_ALIGN_BYTES",
    "_POINTER_SIZE_BYTES",
    "field_mojo_name",
    "mojo_align_decorator_ok",
    "mojo_float_literal_text",
    "scalar_comment_name",
]
