"""Backend-neutral layout and struct-index helpers."""

from __future__ import annotations

from mojo_bindgen.analysis.type_walk import (
    TypeWalkOptions,
    any_type_node,
    iter_type_nodes,
)
from mojo_bindgen.codegen.mojo_mapper import (
    map_atomic_type,
    map_complex_simd,
    map_vector_simd,
)
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    ComplexType,
    EnumRef,
    Field,
    FloatType,
    FunctionPtr,
    IntType,
    OpaqueRecordRef,
    Pointer,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Unit,
    UnsupportedType,
    VectorType,
)


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map struct ``decl_id`` to :class:`Struct`, including incomplete non-unions."""
    out: dict[str, Struct] = {}
    for decl in unit.decls:
        if isinstance(decl, Struct) and not decl.is_union:
            out[decl.decl_id] = decl
    return out


def build_register_passable_map(struct_by_id: dict[str, Struct]) -> dict[str, bool]:
    """Memoized register-passability for each complete struct ``decl_id``."""
    cache: dict[str, bool] = {}
    computing: set[str] = set()

    def passable_for_struct(decl_id: str) -> bool:
        if decl_id in cache:
            return cache[decl_id]
        if decl_id in computing:
            return False
        struct_decl = struct_by_id.get(decl_id)
        if struct_decl is None or struct_decl.is_union or not struct_decl.is_complete:
            cache[decl_id] = False
            return False
        computing.add(decl_id)
        try:
            ok = all(field_ok_cached(field.type) for field in struct_decl.fields)
        finally:
            computing.remove(decl_id)
        cache[decl_id] = ok
        return ok

    def field_ok_cached(t: Type) -> bool:
        if isinstance(t, TypeRef):
            return field_ok_cached(t.canonical)
        if isinstance(t, AtomicType):
            if map_atomic_type(t) is not None:
                return False
            return field_ok_cached(t.value_type)
        if isinstance(t, (IntType, FloatType, EnumRef, OpaqueRecordRef, FunctionPtr)):
            return True
        if isinstance(t, UnsupportedType):
            return False
        if isinstance(t, VectorType):
            return map_vector_simd(t) is not None
        if isinstance(t, ComplexType):
            return map_complex_simd(t) is not None
        if isinstance(t, StructRef):
            return passable_for_struct(t.decl_id)
        if isinstance(t, Pointer):
            if t.pointee is None:
                return True
            return field_ok_cached(t.pointee)
        if isinstance(t, Array):
            return t.array_kind != "fixed" and field_ok_cached(t.element)
        walk = iter_type_nodes(
            t,
            options=TypeWalkOptions(
                peel_typeref=False,
                peel_qualified=True,
                peel_atomic=False,
                descend_pointer=False,
                descend_array=False,
                descend_function_ptr=False,
                descend_vector_element=False,
            ),
        )
        for node in walk:
            if node is not t:
                return field_ok_cached(node)
        return False

    for decl_id in struct_by_id:
        passable_for_struct(decl_id)
    return cache


_EMBEDDED_ATOMIC_WALK = TypeWalkOptions(
    peel_typeref=True,
    peel_qualified=True,
    peel_atomic=False,
    descend_pointer=False,
    descend_array=True,
    descend_function_ptr=False,
    descend_vector_element=False,
)


def is_pure_bitfield_struct(decl: Struct) -> bool:
    return bool(decl.fields) and all(field.is_bitfield for field in decl.fields)


def field_contains_representable_atomic_storage(field: Field) -> bool:
    return any_type_node(
        field.type,
        lambda node: isinstance(node, AtomicType) and map_atomic_type(node) is not None,
        options=_EMBEDDED_ATOMIC_WALK,
    )
