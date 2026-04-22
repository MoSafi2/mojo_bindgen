"""Shared helpers for Mojo analysis modules."""

from __future__ import annotations

from functools import cache

from mojo_bindgen.ir import Field, FloatType, IntType, VoidType

_MOJO_MAX_ALIGN_BYTES = 1 << 29


_MOJO_RESERVED = frozenset(
    """
    def struct fn var let inout out mut ref copy owned deinit self Self import from as
    pass return raise raises try except finally with if elif else for while break continue
    and or not is in del alias comptime True False None
    """.split()
)


def mojo_ident(name: str, *, fallback: str = "field") -> str:
    """Map a C identifier to a safe Mojo name."""
    if not name or not name.strip():
        return fallback
    out = []
    for i, ch in enumerate(name):
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out)
    if s and s[0].isdigit():
        s = "_" + s
    if not s:
        s = fallback
    if s in _MOJO_RESERVED:
        s = s + "_"
    return s


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
