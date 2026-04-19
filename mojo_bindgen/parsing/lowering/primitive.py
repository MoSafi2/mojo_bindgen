"""Clang scalar type lowering to IR primitives."""

from __future__ import annotations

import re

import clang.cindex as cx

from mojo_bindgen.ir import FloatKind, FloatType, IntKind, IntType, Type, VoidType

_QUALIFIER_RE = re.compile(r"\b(?:const|volatile|restrict)\b")
_EXT_INT_RE = re.compile(r"(?:_BitInt|_ExtInt)\s*\(\s*(\d+)\s*\)")

_INT_KIND_BY_TYPE: dict[cx.TypeKind, IntKind] = {
    cx.TypeKind.BOOL: IntKind.BOOL,
    cx.TypeKind.SCHAR: IntKind.SCHAR,
    cx.TypeKind.UCHAR: IntKind.UCHAR,
    cx.TypeKind.SHORT: IntKind.SHORT,
    cx.TypeKind.USHORT: IntKind.USHORT,
    cx.TypeKind.INT: IntKind.INT,
    cx.TypeKind.UINT: IntKind.UINT,
    cx.TypeKind.LONG: IntKind.LONG,
    cx.TypeKind.ULONG: IntKind.ULONG,
    cx.TypeKind.LONGLONG: IntKind.LONGLONG,
    cx.TypeKind.ULONGLONG: IntKind.ULONGLONG,
    cx.TypeKind.INT128: IntKind.INT128,
    cx.TypeKind.UINT128: IntKind.UINT128,
    cx.TypeKind.WCHAR: IntKind.WCHAR,
    cx.TypeKind.CHAR16: IntKind.CHAR16,
    cx.TypeKind.CHAR32: IntKind.CHAR32,
}

_FLOAT_KIND_BY_TYPE: dict[cx.TypeKind, FloatKind] = {
    cx.TypeKind.HALF: FloatKind.FLOAT16,
    cx.TypeKind.FLOAT: FloatKind.FLOAT,
    cx.TypeKind.DOUBLE: FloatKind.DOUBLE,
    cx.TypeKind.LONGDOUBLE: FloatKind.LONG_DOUBLE,
}


def default_signed_int_primitive() -> IntType:
    """Return the parser's default signed int primitive fallback."""
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _normalize_spelling(spelling: str) -> str:
    return " ".join(_QUALIFIER_RE.sub("", spelling).split())


def _size_and_align(clang_type: cx.Type) -> tuple[int, int | None]:
    size = clang_type.get_size()
    align = clang_type.get_align()
    return (size if size > 0 else 0, align if align > 0 else None)


def _char_int_kind(clang_type: cx.Type, norm: str) -> IntKind | None:
    if norm != "char":
        return None
    if clang_type.kind == cx.TypeKind.CHAR_S:
        return IntKind.CHAR_S
    if clang_type.kind == cx.TypeKind.CHAR_U:
        return IntKind.CHAR_U
    return None


def _ext_int_bits(norm: str) -> int | None:
    match = _EXT_INT_RE.search(norm)
    return int(match.group(1)) if match else None


class PrimitiveResolver:
    """Stateless lowering of clang scalar types to IR primitives."""

    def resolve_primitive(self, clang_type: cx.Type) -> Type | None:
        """Return a scalar IR node for scalar clang types, else ``None``."""
        canonical = clang_type.get_canonical()
        norm = _normalize_spelling(canonical.spelling)
        size_bytes, align_bytes = _size_and_align(canonical)

        if canonical.kind == cx.TypeKind.VOID:
            return VoidType()

        if "__float128" in norm or "_Float128" in norm:
            return FloatType(
                float_kind=FloatKind.FLOAT128,
                size_bytes=size_bytes,
                align_bytes=align_bytes,
            )

        float_kind = _FLOAT_KIND_BY_TYPE.get(canonical.kind)
        if float_kind is not None:
            return FloatType(
                float_kind=float_kind,
                size_bytes=size_bytes,
                align_bytes=align_bytes,
            )

        int_kind = _char_int_kind(canonical, norm)
        if int_kind is None:
            int_kind = _INT_KIND_BY_TYPE.get(canonical.kind)

        if int_kind is not None:
            return IntType(
                int_kind=int_kind,
                size_bytes=size_bytes,
                align_bytes=align_bytes,
                ext_bits=_ext_int_bits(norm),
            )

        if _ext_int_bits(norm) is not None:
            return IntType(
                int_kind=IntKind.EXT_INT,
                size_bytes=size_bytes,
                align_bytes=align_bytes,
                ext_bits=_ext_int_bits(norm),
            )

        return None
