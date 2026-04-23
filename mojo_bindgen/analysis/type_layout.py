"""Pure CIR-level layout queries used by record analysis."""

from __future__ import annotations

from mojo_bindgen.ir import (
    Array,
    AtomicType,
    ComplexType,
    EnumRef,
    FloatType,
    FunctionPtr,
    IntType,
    OpaqueRecordRef,
    Pointer,
    QualifiedType,
    StructRef,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
)


def peel_layout_wrappers(t: Type) -> Type:
    """Strip layout-transparent wrappers from a CIR type."""
    while isinstance(t, (TypeRef, QualifiedType, AtomicType)):
        if isinstance(t, TypeRef):
            t = t.canonical
        elif isinstance(t, QualifiedType):
            t = t.unqualified
        else:  # AtomicType
            t = t.value_type
    return t


def type_layout(t: Type) -> tuple[int, int] | None:
    """Return ``(size_bytes, align_bytes)`` for ``t``, or ``None`` if unknown."""
    return _layout_of(peel_layout_wrappers(t))


def type_align(t: Type) -> int | None:
    """Return alignment in bytes for ``t``, or ``None`` if unknown."""
    layout = type_layout(t)
    return None if layout is None else layout[1]


def _layout_of(t: Type) -> tuple[int, int] | None:
    t = peel_layout_wrappers(t)

    if isinstance(
        t,
        (
            IntType,
            FloatType,
            VectorType,
            StructRef,
            Pointer,
            FunctionPtr,
            OpaqueRecordRef,
            UnsupportedType,
            Array,
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


def _explicit_layout(
    size_bytes: int | None,
    align_bytes: int | None,
) -> tuple[int, int] | None:
    if size_bytes is None or align_bytes is None:
        return None
    return size_bytes, align_bytes
