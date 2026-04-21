"""Backend-neutral layout and struct-index helpers."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.codegen._struct_order import toposort_structs
from mojo_bindgen.codegen.mojo_mapper import (
    map_atomic_type,
    map_complex_simd,
    map_vector_simd,
    peel_wrappers,
)
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    ComplexType,
    EnumRef,
    Field,
    FloatType,
    FunctionPtr,
    IntKind,
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
from mojo_bindgen.analysis.type_walk import (
    TypeWalkOptions,
    any_type_node,
    iter_type_nodes,
)


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map struct ``decl_id`` to :class:`Struct`, including incomplete non-unions."""
    out: dict[str, Struct] = {}
    for decl in unit.decls:
        if isinstance(decl, Struct) and not decl.is_union:
            out[decl.decl_id] = decl
    return out


def ordered_struct_decls(unit: Unit) -> tuple[Struct, ...]:
    """Complete non-union structs in dependency order."""
    struct_decls = [
        d for d in unit.decls if isinstance(d, Struct) and not d.is_union and d.is_complete
    ]
    return tuple(toposort_structs(struct_decls))


def incomplete_struct_decls(unit: Unit) -> tuple[Struct, ...]:
    """Forward-declared incomplete non-union structs in declaration order."""
    return tuple(
        d for d in unit.decls if isinstance(d, Struct) and not d.is_union and not d.is_complete
    )


def _type_ok_for_register_passable_field(
    t: Type,
    struct_by_id: dict[str, Struct],
    visiting: set[str] | None = None,
) -> bool:
    if visiting is None:
        visiting = set()
    if isinstance(t, TypeRef):
        return _type_ok_for_register_passable_field(t.canonical, struct_by_id, visiting)
    if isinstance(t, AtomicType):
        if map_atomic_type(t) is not None:
            return False
        return _type_ok_for_register_passable_field(t.value_type, struct_by_id, visiting)
    if isinstance(t, (IntType, FloatType, EnumRef, OpaqueRecordRef, FunctionPtr)):
        return True
    if isinstance(t, UnsupportedType):
        return False
    if isinstance(t, VectorType):
        return map_vector_simd(t) is not None
    if isinstance(t, ComplexType):
        return map_complex_simd(t) is not None
    if isinstance(t, StructRef):
        if t.decl_id in visiting:
            return False
        struct_decl = struct_by_id.get(t.decl_id)
        if struct_decl is None or struct_decl.is_union or not struct_decl.is_complete:
            return False
        visiting.add(t.decl_id)
        try:
            return all(
                _type_ok_for_register_passable_field(field.type, struct_by_id, visiting)
                for field in struct_decl.fields
            )
        finally:
            visiting.remove(t.decl_id)
    if isinstance(t, Pointer):
        if t.pointee is None:
            return True
        return _type_ok_for_register_passable_field(t.pointee, struct_by_id, visiting)
    if isinstance(t, Array):
        return t.array_kind != "fixed" and _type_ok_for_register_passable_field(
            t.element, struct_by_id, visiting
        )
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
            return _type_ok_for_register_passable_field(node, struct_by_id, visiting)
    return False


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


def struct_decl_register_passable(decl: Struct, struct_by_id: dict[str, Struct]) -> bool:
    if decl.is_union or not decl.is_complete:
        return False
    return all(
        _type_ok_for_register_passable_field(field.type, struct_by_id, None)
        for field in decl.fields
    )


_EMBEDDED_ATOMIC_WALK = TypeWalkOptions(
    peel_typeref=True,
    peel_qualified=True,
    peel_atomic=False,
    descend_pointer=False,
    descend_array=True,
    descend_function_ptr=False,
    descend_vector_element=False,
)


def field_contains_representable_atomic_storage(field: Field) -> bool:
    return any_type_node(
        field.type,
        lambda node: isinstance(node, AtomicType) and map_atomic_type(node) is not None,
        options=_EMBEDDED_ATOMIC_WALK,
    )


def struct_has_representable_atomic_storage(decl: Struct) -> bool:
    return any(field_contains_representable_atomic_storage(field) for field in decl.fields)


def is_pure_bitfield_struct(decl: Struct) -> bool:
    return bool(decl.fields) and all(field.is_bitfield for field in decl.fields)


def bitfield_storage_width_bits(field: Field) -> int | None:
    core = peel_wrappers(field.type)
    if not isinstance(core, IntType):
        return None
    return core.size_bytes * 8 if core.size_bytes > 0 else None


def bitfield_unsigned_storage_type(field: Field) -> IntType | None:
    core = peel_wrappers(field.type)
    if not isinstance(core, IntType):
        return None
    unsigned_kind = {
        IntKind.BOOL: IntKind.UCHAR,
        IntKind.CHAR_S: IntKind.CHAR_U,
        IntKind.CHAR_U: IntKind.CHAR_U,
        IntKind.SCHAR: IntKind.UCHAR,
        IntKind.UCHAR: IntKind.UCHAR,
        IntKind.SHORT: IntKind.USHORT,
        IntKind.USHORT: IntKind.USHORT,
        IntKind.INT: IntKind.UINT,
        IntKind.UINT: IntKind.UINT,
        IntKind.LONG: IntKind.ULONG,
        IntKind.ULONG: IntKind.ULONG,
        IntKind.LONGLONG: IntKind.ULONGLONG,
        IntKind.ULONGLONG: IntKind.ULONGLONG,
        IntKind.INT128: IntKind.UINT128,
        IntKind.UINT128: IntKind.UINT128,
        IntKind.WCHAR: IntKind.WCHAR,
        IntKind.CHAR16: IntKind.CHAR16,
        IntKind.CHAR32: IntKind.CHAR32,
        IntKind.EXT_INT: IntKind.EXT_INT,
    }.get(core.int_kind)
    if unsigned_kind is None:
        return None
    return IntType(
        int_kind=unsigned_kind,
        size_bytes=core.size_bytes,
        align_bytes=core.align_bytes,
        ext_bits=core.ext_bits,
    )


def bitfield_field_is_signed(field: Field) -> bool:
    core = peel_wrappers(field.type)
    if not isinstance(core, IntType):
        return False
    return core.int_kind not in {
        IntKind.BOOL,
        IntKind.CHAR_U,
        IntKind.UCHAR,
        IntKind.USHORT,
        IntKind.UINT,
        IntKind.ULONG,
        IntKind.ULONGLONG,
        IntKind.UINT128,
        IntKind.CHAR16,
        IntKind.CHAR32,
    }


def bitfield_field_is_bool(field: Field) -> bool:
    core = peel_wrappers(field.type)
    return isinstance(core, IntType) and core.int_kind == IntKind.BOOL


@dataclass(frozen=True)
class LayoutFacts:
    struct_map: dict[str, Struct]
    ordered_structs: tuple[Struct, ...]
    incomplete_structs: tuple[Struct, ...]
    register_passable_by_decl_id: dict[str, bool]


class ComputeLayoutFactsPass:
    """Compute reusable layout/index facts over normalized IR."""

    def run(self, unit: Unit) -> LayoutFacts:
        struct_map = struct_by_decl_id(unit)
        return LayoutFacts(
            struct_map=struct_map,
            ordered_structs=ordered_struct_decls(unit),
            incomplete_structs=incomplete_struct_decls(unit),
            register_passable_by_decl_id=build_register_passable_map(struct_map),
        )
