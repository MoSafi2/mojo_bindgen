"""Shared helper functions used by analysis and Mojo codegen."""

from __future__ import annotations

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


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _mojo_align_decorator_ok(align_bytes: int) -> bool:
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)


def mojo_float_literal_text(c_spelling: str) -> str:
    text = c_spelling.rstrip()
    while text and text[-1] in "fFlL":
        text = text[:-1]
    return text


__all__ = [
    "_mojo_align_decorator_ok",
    "mojo_float_literal_text",
    "mojo_ident",
]
