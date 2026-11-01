"""Pure CIR-level layout queries used by record analysis."""

from __future__ import annotations

from typing import assert_never

from mojo_bindgen.ir import (
    AtomicType,
    CArray,
    CFunctionPtr,
    ComplexType,
    CPointer,
    CType,
    EnumRef,
    FloatType,
    IntType,
    OpaqueRecordRef,
    QualifiedType,
    StructRef,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)


def peel_layout_wrappers(t: CType) -> CType:
    """Strip layout-transparent wrappers from a CIR type."""
    while isinstance(t, (TypeRef, QualifiedType)):
        if isinstance(t, TypeRef):
            t = t.canonical
        elif isinstance(t, QualifiedType):
            t = t.unqualified
    return t


def type_layout(t: CType) -> tuple[int, int] | None:
    """Return ``(size_bytes, align_bytes)`` for ``t``, or ``None`` if unknown."""
    return _layout_of(peel_layout_wrappers(t))


def type_align(t: CType) -> int | None:
    """Return alignment in bytes for ``t``, or ``None`` if unknown."""
    layout = type_layout(t)
    return None if layout is None else layout[1]


def _layout_of(t: CType) -> tuple[int, int] | None:
    t = peel_layout_wrappers(t)

    if isinstance(t, AtomicType):
        return _explicit_layout(t.size_bytes, t.align_bytes) or type_layout(t.value_type)

    if isinstance(
        t,
        (
            IntType,
            FloatType,
            VectorType,
            StructRef,
            CPointer,
            CFunctionPtr,
            OpaqueRecordRef,
            UnsupportedType,
            CArray,
        ),
    ):
        return _explicit_layout(t.size_bytes, t.align_bytes)

    if isinstance(t, EnumRef):
        return type_layout(t.underlying)

    if isinstance(t, ComplexType):
        if t.align_bytes is not None:
            return t.size_bytes, t.align_bytes
        elem = type_layout(t.element)
        if elem is None:
            return None
        _, elem_align = elem
        return t.size_bytes, elem_align
    if isinstance(t, (TypeRef, QualifiedType)):
        return type_layout(t)
    if isinstance(t, VoidType):
        return None
    assert_never(t)


def _explicit_layout(
    size_bytes: int | None,
    align_bytes: int | None,
) -> tuple[int, int] | None:
    if size_bytes is None or align_bytes is None:
        return None
    return size_bytes, align_bytes
