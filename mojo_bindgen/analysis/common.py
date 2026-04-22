"""Shared helpers for Mojo analysis modules."""

from __future__ import annotations

from functools import cache

from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.ir import Field, FloatType, IntType, VoidType

_MOJO_MAX_ALIGN_BYTES = 1 << 29


@cache
def _legacy_default_target_abi():
    # Legacy analysis still imports these names directly. Keep that path working
    # without relying on the Python host ABI.
    from mojo_bindgen.parsing.frontend import _default_system_compile_args
    from mojo_bindgen.parsing.target_abi import probe_target_abi

    return probe_target_abi(_default_system_compile_args())


def __getattr__(name: str) -> int:
    if name == "_POINTER_SIZE_BYTES":
        return _legacy_default_target_abi().pointer_size_bytes
    if name == "_POINTER_ALIGN_BYTES":
        return _legacy_default_target_abi().pointer_align_bytes
    raise AttributeError(name)


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _mojo_align_decorator_ok(align_bytes: int) -> bool:
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
    "field_mojo_name",
    "_mojo_align_decorator_ok",
    "mojo_float_literal_text",
    "scalar_comment_name",
]
