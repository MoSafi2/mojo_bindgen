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
    Struct,
    StructRef,
    TargetABI,
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
    *,
    target_abi: TargetABI,
    record_map: dict[str, Struct],
) -> tuple[int, int] | None:
    """Return CIR size/alignment facts for ``t`` or ``None`` when unavailable."""

    return _type_layout_worker(
        peel_layout_wrappers(t),
        record_map=record_map,
        target_abi=target_abi,
        visiting=set(),
    )


def _type_layout_worker(
    t: Type,
    *,
    record_map: dict[str, Struct],
    target_abi: TargetABI,
    visiting: set[str],
) -> tuple[int, int] | None:
    if isinstance(t, IntType):
        return t.size_bytes, t.align_bytes or t.size_bytes
    if isinstance(t, FloatType):
        return t.size_bytes, t.align_bytes or t.size_bytes
    if isinstance(t, EnumRef):
        return _type_layout_worker(
            peel_layout_wrappers(t.underlying),
            record_map=record_map,
            target_abi=target_abi,
            visiting=visiting,
        )
    if isinstance(t, (Pointer, FunctionPtr, OpaqueRecordRef)):
        return target_abi.pointer_size_bytes, target_abi.pointer_align_bytes
    if isinstance(t, UnsupportedType):
        if t.size_bytes is None or t.align_bytes is None:
            return None
        return t.size_bytes, t.align_bytes
    if isinstance(t, ComplexType):
        return t.size_bytes, t.element.align_bytes or t.element.size_bytes
    if isinstance(t, VectorType):
        element_layout = _type_layout_worker(
            peel_layout_wrappers(t.element),
            record_map=record_map,
            target_abi=target_abi,
            visiting=visiting,
        )
        if element_layout is None:
            return t.size_bytes, t.size_bytes
        _, element_align = element_layout
        return t.size_bytes, max(
            element_align,
            t.size_bytes if t.is_ext_vector else element_align,
        )
    if isinstance(t, StructRef):
        if t.decl_id in visiting:
            return None
        target = record_map.get(t.decl_id)
        if target is None:
            return None
        visiting.add(t.decl_id)
        try:
            return target.size_bytes, target.align_bytes
        finally:
            visiting.remove(t.decl_id)
    if isinstance(t, Array):
        if t.array_kind != "fixed" or t.size is None:
            return target_abi.pointer_size_bytes, target_abi.pointer_align_bytes
        element_layout = _type_layout_worker(
            peel_layout_wrappers(t.element),
            record_map=record_map,
            target_abi=target_abi,
            visiting=visiting,
        )
        if element_layout is None:
            return None
        element_size, element_align = element_layout
        return element_size * t.size, element_align
    return None
