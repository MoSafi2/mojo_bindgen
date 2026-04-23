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
    """Remove wrappers that do not affect CIR layout facts."""

    while True:
        if isinstance(t, TypeRef):
            t = t.canonical
            continue
        if isinstance(t, QualifiedType):
            t = t.unqualified
            continue
        if isinstance(t, AtomicType):
            t = t.value_type
            continue
        return t


def type_layout(
    t: Type,
) -> tuple[int, int] | None:
    """Return CIR size/alignment facts for ``t`` or ``None`` when unavailable."""

    return _type_layout_worker(peel_layout_wrappers(t))


def type_align(
    t: Type,
) -> int | None:
    """Return CIR alignment facts for ``t`` or ``None`` when unavailable."""

    layout = type_layout(t)
    if layout is None:
        return None
    _, align_bytes = layout
    return align_bytes


def _type_layout_worker(t: Type) -> tuple[int, int] | None:
    if isinstance(t, IntType):
        return t.size_bytes, t.align_bytes or t.size_bytes
    if isinstance(t, FloatType):
        return t.size_bytes, t.align_bytes or t.size_bytes
    if isinstance(t, EnumRef):
        return _type_layout_worker(peel_layout_wrappers(t.underlying))
    if isinstance(t, (Pointer, FunctionPtr, OpaqueRecordRef)):
        if t.align_bytes is None:
            return None
        return t.size_bytes, t.align_bytes
    if isinstance(t, UnsupportedType):
        if t.size_bytes is None or t.align_bytes is None:
            return None
        return t.size_bytes, t.align_bytes
    if isinstance(t, ComplexType):
        if t.align_bytes is not None:
            return t.size_bytes, t.align_bytes
        return t.size_bytes, t.element.align_bytes or t.element.size_bytes
    if isinstance(t, VectorType):
        if t.align_bytes is not None:
            return t.size_bytes, t.align_bytes
        element_layout = _type_layout_worker(peel_layout_wrappers(t.element))
        if element_layout is None:
            return None
        _, element_align = element_layout
        return t.size_bytes, element_align
    if isinstance(t, StructRef):
        if t.align_bytes is None:
            return None
        return t.size_bytes, t.align_bytes
    if isinstance(t, Array):
        if t.align_bytes is not None:
            return t.size_bytes, t.align_bytes
        if t.array_kind != "fixed" or t.size is None:
            return None
        element_layout = _type_layout_worker(peel_layout_wrappers(t.element))
        if element_layout is None:
            return None
        element_size, element_align = element_layout
        return element_size * t.size, element_align
    return None
