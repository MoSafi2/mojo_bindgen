"""Final semantic analysis pass producing AnalyzedUnit."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.codegen._struct_order import toposort_structs
from mojo_bindgen.codegen.mojo_emit_options import FFIScalarStyle, MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import (
    FFIOriginStyle,
    TypeMapper,
    map_atomic_type,
    map_complex_simd,
    map_vector_simd,
    mojo_ident,
    peel_wrappers,
)
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    ComplexType,
    Const,
    Enum,
    EnumRef,
    Field,
    FloatType,
    Function,
    FunctionPtr,
    GlobalVar,
    IntKind,
    IntType,
    MacroDecl,
    OpaqueRecordRef,
    Pointer,
    QualifiedType,
    Struct,
    StructRef,
    Type,
    Typedef,
    TypeRef,
    Unit,
    UnsupportedType,
    VectorType,
)

_MOJO_MAX_ALIGN_BYTES = 1 << 29

# --- Analyzed* IR -----------------------------------------------------------------


@dataclass(frozen=True)
class AnalyzedField:
    """Derived field metadata needed by the renderer."""

    field: Field
    index: int
    mojo_name: str
    callback_alias_name: str | None = None


@dataclass(frozen=True)
class AnalyzedBitfieldStorage:
    """One synthesized physical storage member for a pure bitfield struct."""

    name: str
    type: Type
    byte_offset: int
    start_bit: int
    width_bits: int


@dataclass(frozen=True)
class AnalyzedBitfieldMember:
    """One logical named bitfield projected onto a synthesized storage member."""

    field: Field
    mojo_name: str
    storage_name: str
    storage_type: Type
    storage_local_bit_offset: int
    bit_width: int
    is_signed: bool
    is_bool: bool


@dataclass(frozen=True)
class AnalyzedPureBitfieldStruct:
    """Derived storage/member split for a pure bitfield struct."""

    storages: tuple[AnalyzedBitfieldStorage, ...]
    members: tuple[AnalyzedBitfieldMember, ...]


@dataclass(frozen=True)
class AnalyzedStruct:
    """Derived struct-level emission decisions."""

    decl: Struct
    register_passable: bool
    align_decorator: int | None
    align_stride_warning: bool
    align_omit_comment: str | None
    fields: tuple[AnalyzedField, ...]
    pure_bitfield: AnalyzedPureBitfieldStruct | None = None


@dataclass(frozen=True)
class AnalyzedTypedef:
    """Derived typedef policy."""

    decl: Typedef
    skip_duplicate: bool
    callback_alias_name: str | None = None


FunctionKind = Literal["wrapper", "variadic_stub", "non_register_return_stub"]


@dataclass(frozen=True)
class AnalyzedFunction:
    """Derived function emission decisions."""

    decl: Function
    kind: FunctionKind
    param_names: tuple[str, ...]
    ret_callback_alias_name: str | None = None
    param_callback_alias_names: tuple[str | None, ...] = ()


@dataclass(frozen=True)
class CallbackAlias:
    """Generated callback signature alias for a surfaced function-pointer type."""

    name: str
    fp: FunctionPtr


@dataclass(frozen=True)
class AnalyzedUnion:
    """Derived union lowering decisions."""

    decl: Struct
    uses_unsafe_union: bool


GlobalVarKind = Literal["wrapper", "stub"]


@dataclass(frozen=True)
class AnalyzedGlobalVar:
    """Derived global variable emission policy."""

    decl: GlobalVar
    kind: GlobalVarKind
    """``wrapper``: emit ``GlobalVar`` / ``GlobalConst`` helpers; ``stub``: comment-only."""

    surface_type: str
    """Mojo surface type used for ``GlobalVar[T=..., link=...]`` (wrapper) or comments (stub)."""

    stub_reason: str | None = None


TailDecl = Enum | Const | MacroDecl | AnalyzedGlobalVar | AnalyzedTypedef | AnalyzedFunction


@dataclass(frozen=True)
class AnalyzedUnit:
    """Unit-level semantic analysis for Mojo generation."""

    unit: Unit
    opts: MojoEmitOptions
    needs_opaque_imports: bool
    needs_simd_import: bool
    needs_complex_import: bool
    needs_atomic_import: bool
    needs_global_symbol_helpers: bool
    """True when at least one global uses ``OwnedDLHandle.get_symbol`` (wrapper globals)."""

    semantic_fallback_notes: tuple[str, ...]
    unsafe_union_names: frozenset[str]
    emitted_typedef_mojo_names: frozenset[str]
    callback_aliases: tuple[CallbackAlias, ...]
    callback_signature_names: frozenset[str]
    global_callback_aliases: dict[str, str]
    ordered_incomplete_structs: tuple[AnalyzedStruct, ...]
    ordered_structs: tuple[AnalyzedStruct, ...]
    unions: tuple[AnalyzedUnion, ...]
    tail_decls: tuple[TailDecl, ...]
    ffi_scalar_import_names: frozenset[str]
    """``c_int`` / ``c_long`` / … imported from ``std.ffi`` (empty when using ``fixed_width``)."""


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def mojo_align_decorator_ok(align_bytes: int) -> bool:
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map struct ``decl_id`` to :class:`Struct`, including incomplete (opaque) records."""
    out: dict[str, Struct] = {}
    for d in unit.decls:
        if isinstance(d, Struct) and not d.is_union:
            out[d.decl_id] = d
    return out


# --- Type traversal + import / fallback queries ------------------------------------


def _iter_type_nodes_opaque_import(t: Type) -> Iterator[Type]:
    """Preorder; does not descend into FunctionPtr children (opaque-import semantics)."""
    yield t
    if isinstance(t, TypeRef):
        yield from _iter_type_nodes_opaque_import(t.canonical)
    elif isinstance(t, QualifiedType):
        yield from _iter_type_nodes_opaque_import(t.unqualified)
    elif isinstance(t, AtomicType):
        yield from _iter_type_nodes_opaque_import(t.value_type)
    elif isinstance(t, EnumRef):
        return
    elif isinstance(t, Pointer):
        if t.pointee is None:
            return
        yield from _iter_type_nodes_opaque_import(t.pointee)
    elif isinstance(t, Array):
        yield from _iter_type_nodes_opaque_import(t.element)
    elif isinstance(t, FunctionPtr):
        return


def _iter_type_nodes_imports(t: Type) -> Iterator[Type]:
    """Preorder for SIMD/complex/atomic import checks (recurses through FunctionPtr)."""
    yield t
    if isinstance(t, TypeRef):
        yield from _iter_type_nodes_imports(t.canonical)
    elif isinstance(t, QualifiedType):
        yield from _iter_type_nodes_imports(t.unqualified)
    elif isinstance(t, AtomicType):
        yield from _iter_type_nodes_imports(t.value_type)
    elif isinstance(t, Pointer):
        if t.pointee is not None:
            yield from _iter_type_nodes_imports(t.pointee)
    elif isinstance(t, Array):
        yield from _iter_type_nodes_imports(t.element)
    elif isinstance(t, FunctionPtr):
        yield from _iter_type_nodes_imports(t.ret)
        for p in t.params:
            yield from _iter_type_nodes_imports(p)


def _iter_type_nodes_fallbacks(t: Type) -> Iterator[Type]:
    """Preorder matching :func:`_note_semantic_fallbacks` traversal."""
    yield t
    if isinstance(t, TypeRef):
        yield from _iter_type_nodes_fallbacks(t.canonical)
    elif isinstance(t, QualifiedType):
        yield from _iter_type_nodes_fallbacks(t.unqualified)
    elif isinstance(t, AtomicType):
        yield from _iter_type_nodes_fallbacks(t.value_type)
    elif isinstance(t, Pointer):
        if t.pointee is not None:
            yield from _iter_type_nodes_fallbacks(t.pointee)
    elif isinstance(t, Array):
        yield from _iter_type_nodes_fallbacks(t.element)
    elif isinstance(t, FunctionPtr):
        yield from _iter_type_nodes_fallbacks(t.ret)
        for p in t.params:
            yield from _iter_type_nodes_fallbacks(p)
    elif isinstance(t, ComplexType):
        return
    elif isinstance(t, VectorType):
        yield from _iter_type_nodes_fallbacks(t.element)


def _type_needs_opaque_pointer_import(t: Type) -> bool:
    for u in _iter_type_nodes_opaque_import(t):
        if isinstance(u, Pointer) and u.pointee is None:
            return True
        if isinstance(u, FunctionPtr):
            return True
        if isinstance(u, (OpaqueRecordRef, UnsupportedType)):
            return True
    return False


def _type_needs_simd_import(t: Type) -> bool:
    return any(
        isinstance(u, VectorType) and map_vector_simd(u) is not None
        for u in _iter_type_nodes_imports(t)
    )


def _type_needs_complex_import(t: Type) -> bool:
    return any(
        isinstance(u, ComplexType) and map_complex_simd(u) is not None
        for u in _iter_type_nodes_imports(t)
    )


def _type_needs_atomic_import(t: Type) -> bool:
    return any(
        isinstance(u, AtomicType) and map_atomic_type(u) is not None
        for u in _iter_type_nodes_imports(t)
    )


def _collect_fallback_notes_for_type(t: Type, notes: set[str]) -> None:
    for u in _iter_type_nodes_fallbacks(t):
        if isinstance(u, AtomicType) and map_atomic_type(u) is None:
            notes.add(
                "some atomic types were mapped to their underlying non-atomic Mojo type because Atomic[dtype] was not representable"
            )
        elif isinstance(u, ComplexType) and map_complex_simd(u) is None:
            notes.add(
                "some complex C types were mapped as InlineArray[scalar, 2] because ComplexSIMD[dtype, 1] was not representable"
            )
        elif isinstance(u, VectorType) and map_vector_simd(u) is None:
            notes.add(
                "some vector C types were mapped as InlineArray[...] because SIMD[dtype, size] was not representable"
            )


@dataclass(frozen=True)
class ImportNeeds:
    opaque: bool
    simd: bool
    complex: bool
    atomic: bool


def collect_unit_import_and_fallback_needs(
    unit: Unit,
) -> tuple[ImportNeeds, tuple[str, ...]]:
    """Single scan of ``unit.decls`` for import flags and semantic fallback notes."""
    notes: set[str] = set()
    opaque = simd = complex = atomic = False
    for d in unit.decls:
        if isinstance(d, Struct) and not d.is_union:
            for f in d.fields:
                t = f.type
                opaque = opaque or _type_needs_opaque_pointer_import(t)
                simd = simd or _type_needs_simd_import(t)
                complex = complex or _type_needs_complex_import(t)
                atomic = atomic or _type_needs_atomic_import(t)
                _collect_fallback_notes_for_type(t, notes)
        elif isinstance(d, Function):
            opaque = opaque or _type_needs_opaque_pointer_import(d.ret)
            simd = simd or _type_needs_simd_import(d.ret)
            complex = complex or _type_needs_complex_import(d.ret)
            atomic = atomic or _type_needs_atomic_import(d.ret)
            _collect_fallback_notes_for_type(d.ret, notes)
            for p in d.params:
                t = p.type
                opaque = opaque or _type_needs_opaque_pointer_import(t)
                simd = simd or _type_needs_simd_import(t)
                complex = complex or _type_needs_complex_import(t)
                atomic = atomic or _type_needs_atomic_import(t)
                _collect_fallback_notes_for_type(t, notes)
        elif isinstance(d, Typedef):
            t = d.canonical
            opaque = opaque or _type_needs_opaque_pointer_import(t)
            simd = simd or _type_needs_simd_import(t)
            complex = complex or _type_needs_complex_import(t)
            atomic = atomic or _type_needs_atomic_import(t)
            _collect_fallback_notes_for_type(t, notes)
        elif isinstance(d, GlobalVar):
            t = d.type
            opaque = opaque or _type_needs_opaque_pointer_import(t)
            simd = simd or _type_needs_simd_import(t)
            complex = complex or _type_needs_complex_import(t)
            atomic = atomic or _type_needs_atomic_import(t)
            _collect_fallback_notes_for_type(t, notes)
    return (
        ImportNeeds(opaque=opaque, simd=simd, complex=complex, atomic=atomic),
        tuple(sorted(notes)),
    )


# --- Layout / unions / register passability ----------------------------------------


def _type_ok_for_unsafe_union_member(t: Type) -> bool:
    u = peel_wrappers(t)
    return isinstance(u, (IntType, FloatType, Pointer, FunctionPtr, OpaqueRecordRef))


def _try_unsafe_union_type_list(
    decl: Struct, ffi_origin: FFIOriginStyle, ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases"
) -> list[str] | None:
    if not decl.is_union or not decl.fields:
        return None
    mapper = TypeMapper(
        ffi_origin=ffi_origin,
        unsafe_union_names=frozenset(),
        typedef_mojo_names=frozenset(),
        ffi_scalar_style=ffi_scalar_style,
    )
    mapped_members: list[str] = []
    for f in decl.fields:
        if not _type_ok_for_unsafe_union_member(f.type):
            return None
        mapped_members.append(mapper.canonical(f.type))
    if len(set(mapped_members)) != len(mapped_members):
        return None
    return mapped_members


def eligible_unsafe_union_names(
    unit: Unit, ffi_origin: FFIOriginStyle, ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases"
) -> frozenset[str]:
    out: set[str] = set()
    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            tl = _try_unsafe_union_type_list(d, ffi_origin, ffi_scalar_style)
            if tl is not None:
                out.add(f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union")
    return frozenset(out)


def _type_ok_for_register_passable_field(
    t: Type,
    struct_by_id: dict[str, Struct],
    visiting: set[str] | None = None,
) -> bool:
    if visiting is None:
        visiting = set()
    if isinstance(t, TypeRef):
        return _type_ok_for_register_passable_field(t.canonical, struct_by_id, visiting)
    if isinstance(t, QualifiedType):
        return _type_ok_for_register_passable_field(t.unqualified, struct_by_id, visiting)
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
        s = struct_by_id.get(t.decl_id)
        if s is None or s.is_union or not s.is_complete:
            return False
        visiting.add(t.decl_id)
        try:
            return all(
                _type_ok_for_register_passable_field(f.type, struct_by_id, visiting)
                for f in s.fields
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
        s = struct_by_id.get(decl_id)
        if s is None or s.is_union or not s.is_complete:
            cache[decl_id] = False
            return False
        computing.add(decl_id)
        try:
            ok = all(field_ok_cached(f.type) for f in s.fields)
        finally:
            computing.remove(decl_id)
        cache[decl_id] = ok
        return ok

    def field_ok_cached(t: Type) -> bool:
        if isinstance(t, TypeRef):
            return field_ok_cached(t.canonical)
        if isinstance(t, QualifiedType):
            return field_ok_cached(t.unqualified)
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
        return False

    for decl_id in struct_by_id:
        passable_for_struct(decl_id)
    return cache


def struct_decl_register_passable(decl: Struct, struct_by_id: dict[str, Struct]) -> bool:
    if decl.is_union or not decl.is_complete:
        return False
    return all(
        _type_ok_for_register_passable_field(f.type, struct_by_id, None) for f in decl.fields
    )


def _field_mojo_name(f: Field, index: int) -> str:
    if f.source_name:
        return mojo_ident(f.source_name)
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


def _is_pure_bitfield_struct(decl: Struct) -> bool:
    return bool(decl.fields) and all(field.is_bitfield for field in decl.fields)


def _bitfield_storage_width_bits(field: Field) -> int | None:
    core = peel_wrappers(field.type)
    if not isinstance(core, IntType):
        return None
    return core.size_bytes * 8 if core.size_bytes > 0 else None


def _bitfield_field_is_signed(field: Field) -> bool:
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


def _bitfield_field_is_bool(field: Field) -> bool:
    core = peel_wrappers(field.type)
    return isinstance(core, IntType) and core.int_kind == IntKind.BOOL


def _analyze_pure_bitfield_struct(analyzed_fields: tuple[AnalyzedField, ...]) -> AnalyzedPureBitfieldStruct | None:
    storages: list[AnalyzedBitfieldStorage] = []
    members: list[AnalyzedBitfieldMember] = []
    current: AnalyzedBitfieldStorage | None = None

    for af in analyzed_fields:
        field = af.field
        width_bits = _bitfield_storage_width_bits(field)
        if width_bits is None:
            return None

        if field.bit_width == 0:
            current = None
            continue

        field_end_bit = field.bit_offset + field.bit_width
        if current is None:
            needs_new_storage = True
        else:
            widened_width_bits = max(current.width_bits, width_bits)
            needs_new_storage = (
                field.bit_offset < current.start_bit
                or field_end_bit > current.start_bit + widened_width_bits
            )
        if needs_new_storage:
            storage_start_bit = (field.bit_offset // width_bits) * width_bits
            current = AnalyzedBitfieldStorage(
                name=f"__bf{len(storages)}",
                type=field.type,
                byte_offset=storage_start_bit // 8,
                start_bit=storage_start_bit,
                width_bits=width_bits,
            )
            storages.append(current)
        elif width_bits > current.width_bits:
            current = AnalyzedBitfieldStorage(
                name=current.name,
                type=field.type,
                byte_offset=current.byte_offset,
                start_bit=current.start_bit,
                width_bits=width_bits,
            )
            storages[-1] = current

        if field.is_anonymous:
            continue

        members.append(
            AnalyzedBitfieldMember(
                field=field,
                mojo_name=af.mojo_name,
                storage_name=current.name,
                storage_type=current.type,
                storage_local_bit_offset=field.bit_offset - current.start_bit,
                bit_width=field.bit_width,
                is_signed=_bitfield_field_is_signed(field),
                is_bool=_bitfield_field_is_bool(field),
            )
        )

    return AnalyzedPureBitfieldStruct(storages=tuple(storages), members=tuple(members))


def _ordered_struct_decls(unit: Unit) -> tuple[Struct, ...]:
    struct_decls = [
        d for d in unit.decls if isinstance(d, Struct) and not d.is_union and d.is_complete
    ]
    return tuple(toposort_structs(struct_decls))


def _incomplete_struct_decls(unit: Unit) -> tuple[Struct, ...]:
    """Forward-declared / incomplete non-union structs, in TU declaration order."""
    return tuple(
        d for d in unit.decls if isinstance(d, Struct) and not d.is_union and not d.is_complete
    )


def _emitted_struct_enum_names(
    unit: Unit,
    ordered_structs: tuple[Struct, ...],
    incomplete_structs: tuple[Struct, ...],
) -> frozenset[str]:
    emitted_names: set[str] = set()
    for s in ordered_structs:
        emitted_names.add(mojo_ident(s.name.strip() or s.c_name.strip()))
    for s in incomplete_structs:
        emitted_names.add(mojo_ident(s.name.strip() or s.c_name.strip()))
    for d in unit.decls:
        if isinstance(d, Enum):
            emitted_names.add(mojo_ident(d.name))
    return frozenset(emitted_names)


def _emitted_typedef_mojo_names(
    unit: Unit, emitted_struct_enum_names: frozenset[str]
) -> frozenset[str]:
    return frozenset(
        mojo_ident(d.name)
        for d in unit.decls
        if isinstance(d, Typedef) and mojo_ident(d.name) not in emitted_struct_enum_names
    )


# --- Callback aliases --------------------------------------------------------------


@dataclass(frozen=True)
class CallbackAliasInfo:
    aliases: tuple[CallbackAlias, ...]
    signature_names: frozenset[str]
    field_aliases: dict[tuple[str, int], str]
    typedef_aliases: dict[str, str]
    fn_param_aliases: dict[tuple[str, int], str]
    fn_ret_aliases: dict[str, str]
    global_aliases: dict[str, str]


def _supports_callback_alias(fp: FunctionPtr) -> bool:
    if fp.is_variadic:
        return False
    if fp.calling_convention is None:
        return True
    return fp.calling_convention.lower() in {"c", "cdecl", "default"}


def _function_ptr_from_type(t: Type) -> FunctionPtr | None:
    u = peel_wrappers(t)
    return u if isinstance(u, FunctionPtr) else None


def _unique_callback_alias(base: str, used: set[str]) -> str:
    candidate = mojo_ident(base)
    if candidate not in used:
        used.add(candidate)
        return candidate
    i = 2
    while True:
        named = f"{candidate}_{i}"
        if named not in used:
            used.add(named)
            return named
        i += 1


def _collect_callback_aliases(
    unit: Unit,
    emitted_typedef_names: frozenset[str],
) -> CallbackAliasInfo:
    aliases: list[CallbackAlias] = []
    alias_names: set[str] = set()
    field_aliases: dict[tuple[str, int], str] = {}
    typedef_aliases: dict[str, str] = {}
    fn_param_aliases: dict[tuple[str, int], str] = {}
    fn_ret_aliases: dict[str, str] = {}
    global_aliases: dict[str, str] = {}

    def ensure_alias(fp: FunctionPtr, preferred: str) -> str:
        alias = _unique_callback_alias(preferred, alias_names)
        aliases.append(CallbackAlias(name=alias, fp=fp))
        return alias

    for d in unit.decls:
        if isinstance(d, Typedef):
            fp = _function_ptr_from_type(d.aliased)
            if (
                fp is not None
                and _supports_callback_alias(fp)
                and mojo_ident(d.name) in emitted_typedef_names
            ):
                typedef_aliases[d.decl_id] = ensure_alias(fp, d.name)
        elif isinstance(d, Struct) and not d.is_union:
            base = d.name.strip() or d.c_name.strip()
            for i, field in enumerate(d.fields):
                fp = _function_ptr_from_type(field.type)
                if fp is not None and _supports_callback_alias(fp):
                    field_name = field.source_name or field.name or f"field_{i}"
                    suffix = field_name if field_name.endswith("cb") else f"{field_name}_cb"
                    field_aliases[(d.decl_id, i)] = ensure_alias(fp, f"{base}_{suffix}")
        elif isinstance(d, Function):
            fp = _function_ptr_from_type(d.ret)
            if fp is not None and _supports_callback_alias(fp):
                if isinstance(d.ret, TypeRef) and mojo_ident(d.ret.name) in emitted_typedef_names:
                    fn_ret_aliases[d.decl_id] = mojo_ident(d.ret.name)
                else:
                    fn_ret_aliases[d.decl_id] = ensure_alias(fp, f"{d.name}_return_cb")
            for i, param in enumerate(d.params):
                fp = _function_ptr_from_type(param.type)
                if fp is not None and _supports_callback_alias(fp):
                    if (
                        isinstance(param.type, TypeRef)
                        and mojo_ident(param.type.name) in emitted_typedef_names
                    ):
                        fn_param_aliases[(d.decl_id, i)] = mojo_ident(param.type.name)
                    else:
                        pname = param.name or f"arg{i}"
                        fn_param_aliases[(d.decl_id, i)] = ensure_alias(fp, f"{d.name}_{pname}_cb")
        elif isinstance(d, GlobalVar):
            fp = _function_ptr_from_type(d.type)
            if fp is not None and _supports_callback_alias(fp):
                if isinstance(d.type, TypeRef) and mojo_ident(d.type.name) in emitted_typedef_names:
                    global_aliases[d.decl_id] = mojo_ident(d.type.name)
                else:
                    global_aliases[d.decl_id] = ensure_alias(fp, f"{d.name}_cb")

    return CallbackAliasInfo(
        aliases=tuple(aliases),
        signature_names=frozenset(alias_names),
        field_aliases=field_aliases,
        typedef_aliases=typedef_aliases,
        fn_param_aliases=fn_param_aliases,
        fn_ret_aliases=fn_ret_aliases,
        global_aliases=global_aliases,
    )


# --- Orchestration -----------------------------------------------------------------


@dataclass
class _SemanticContext:
    """Precomputed facts for one :func:`analyze_unit_semantics` run (module-internal)."""

    options: MojoEmitOptions
    struct_map: dict[str, Struct]
    ordered_struct_decls: tuple[Struct, ...]
    emitted_names: frozenset[str]
    emitted_typedef_names: frozenset[str]
    callback_info: CallbackAliasInfo
    unsafe_union_names: frozenset[str]
    register_passable_by_decl_id: dict[str, bool]
    import_needs: ImportNeeds
    semantic_fallback_notes: tuple[str, ...]
    type_mapper: TypeMapper


def _analyze_struct(
    decl: Struct,
    struct_map: dict[str, Struct],
    field_callback_aliases: dict[tuple[str, int], str] | None,
    *,
    register_passable: bool,
) -> AnalyzedStruct:
    align_decorator: int | None = None
    align_stride_warning = False
    align_omit_comment: str | None = None
    ab = decl.align_bytes
    if mojo_align_decorator_ok(ab):
        align_decorator = ab
        if decl.size_bytes % ab != 0:
            align_stride_warning = True
    elif ab > 1:
        align_omit_comment = f"# @align omitted: C align_bytes={ab} is not a valid Mojo @align (power of 2, max 2**29)."
    if decl.is_packed:
        packed_comment = "# packed record: verify Mojo layout against the target C ABI."
        align_omit_comment = (
            packed_comment
            if align_omit_comment is None
            else f"{align_omit_comment} {packed_comment[2:]}"
        )
    fields = tuple(
        AnalyzedField(
            field=f,
            index=i,
            mojo_name=_field_mojo_name(f, i),
            callback_alias_name=(
                None
                if field_callback_aliases is None
                else field_callback_aliases.get((decl.decl_id, i))
            ),
        )
        for i, f in enumerate(decl.fields)
    )
    pure_bitfield = _analyze_pure_bitfield_struct(fields) if _is_pure_bitfield_struct(decl) else None
    return AnalyzedStruct(
        decl=decl,
        register_passable=register_passable,
        align_decorator=align_decorator,
        align_stride_warning=align_stride_warning,
        align_omit_comment=align_omit_comment,
        fields=fields,
        pure_bitfield=pure_bitfield,
    )


def _outer_atomic(t: Type) -> AtomicType | None:
    """Return the outermost :class:`AtomicType` wrapper, if any (before typedef peel)."""

    while True:
        if isinstance(t, AtomicType):
            return t
        if isinstance(t, TypeRef):
            t = t.canonical
            continue
        if isinstance(t, QualifiedType):
            t = t.unqualified
            continue
        return None


def _global_var_stub_reason(decl: GlobalVar) -> str | None:
    """Return a stub reason when thin ``GlobalVar`` wrappers are not emitted."""
    if _outer_atomic(decl.type) is not None:
        return "atomic global requires manual binding (use Atomic APIs on a pointer)"
    core = peel_wrappers(decl.type)
    if isinstance(core, UnsupportedType) and (core.size_bytes is None or core.size_bytes == 0):
        return "unsupported global type layout"
    return None


def _analyze_global_var(
    decl: GlobalVar,
    type_mapper: TypeMapper,
    global_aliases: dict[str, str],
) -> AnalyzedGlobalVar:
    reason = _global_var_stub_reason(decl)
    callback_alias = global_aliases.get(decl.decl_id)
    ty = (
        type_mapper.callback_pointer_type(callback_alias)
        if callback_alias is not None
        else type_mapper.surface(decl.type)
    )
    if reason is not None:
        return AnalyzedGlobalVar(decl=decl, kind="stub", surface_type=ty, stub_reason=reason)
    return AnalyzedGlobalVar(decl=decl, kind="wrapper", surface_type=ty)


def _analyze_function(
    fn: Function,
    struct_map: dict[str, Struct],
    type_mapper: TypeMapper,
    register_passable_by_decl_id: dict[str, bool],
    ret_callback_alias_name: str | None = None,
    param_callback_alias_names: tuple[str | None, ...] = (),
) -> AnalyzedFunction:
    param_names = tuple(type_mapper.param_names(fn.params))
    if fn.is_variadic:
        return AnalyzedFunction(
            decl=fn,
            kind="variadic_stub",
            param_names=param_names,
            ret_callback_alias_name=ret_callback_alias_name,
            param_callback_alias_names=param_callback_alias_names,
        )
    ret_u = peel_wrappers(fn.ret)
    if isinstance(ret_u, StructRef):
        rs = struct_map.get(ret_u.decl_id)
        if rs is not None and not register_passable_by_decl_id.get(rs.decl_id, False):
            return AnalyzedFunction(
                decl=fn,
                kind="non_register_return_stub",
                param_names=param_names,
                ret_callback_alias_name=ret_callback_alias_name,
                param_callback_alias_names=param_callback_alias_names,
            )
    return AnalyzedFunction(
        decl=fn,
        kind="wrapper",
        param_names=param_names,
        ret_callback_alias_name=ret_callback_alias_name,
        param_callback_alias_names=param_callback_alias_names,
    )


def analyze_unit_semantics(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    # Phase A: precompute unit-level semantic facts
    ordered_struct_decls = _ordered_struct_decls(unit)
    incomplete_struct_decls = _incomplete_struct_decls(unit)
    emitted_names = _emitted_struct_enum_names(unit, ordered_struct_decls, incomplete_struct_decls)
    emitted_typedef_names = _emitted_typedef_mojo_names(unit, emitted_names)
    callback_info = _collect_callback_aliases(unit, emitted_typedef_names)
    unsafe_union_names = eligible_unsafe_union_names(
        unit, options.ffi_origin, options.ffi_scalar_style
    )
    struct_map = struct_by_decl_id(unit)
    register_passable_by_decl_id = build_register_passable_map(struct_map)
    import_needs, semantic_fallback_notes = collect_unit_import_and_fallback_needs(unit)
    type_mapper = TypeMapper(
        ffi_origin=options.ffi_origin,
        unsafe_union_names=unsafe_union_names,
        typedef_mojo_names=emitted_typedef_names,
        callback_signature_names=callback_info.signature_names,
        ffi_scalar_style=options.ffi_scalar_style,
    )
    ctx = _SemanticContext(
        options=options,
        struct_map=struct_map,
        ordered_struct_decls=ordered_struct_decls,
        emitted_names=emitted_names,
        emitted_typedef_names=emitted_typedef_names,
        callback_info=callback_info,
        unsafe_union_names=unsafe_union_names,
        register_passable_by_decl_id=register_passable_by_decl_id,
        import_needs=import_needs,
        semantic_fallback_notes=semantic_fallback_notes,
        type_mapper=type_mapper,
    )

    # Phase B: materialize analyzed declarations
    ordered_incomplete_structs = tuple(
        _analyze_struct(
            decl,
            ctx.struct_map,
            ctx.callback_info.field_aliases,
            register_passable=ctx.register_passable_by_decl_id.get(decl.decl_id, False),
        )
        for decl in incomplete_struct_decls
    )
    ordered_structs = tuple(
        _analyze_struct(
            decl,
            ctx.struct_map,
            ctx.callback_info.field_aliases,
            register_passable=ctx.register_passable_by_decl_id.get(decl.decl_id, False),
        )
        for decl in ctx.ordered_struct_decls
    )

    unions = tuple(
        AnalyzedUnion(
            decl=d,
            uses_unsafe_union=f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union"
            in ctx.unsafe_union_names,
        )
        for d in unit.decls
        if isinstance(d, Struct) and d.is_union
    )

    tail_decls: list[TailDecl] = []
    for d in unit.decls:
        if isinstance(d, Typedef):
            tail_decls.append(
                AnalyzedTypedef(
                    decl=d,
                    skip_duplicate=mojo_ident(d.name) in ctx.emitted_names,
                    callback_alias_name=ctx.callback_info.typedef_aliases.get(d.decl_id),
                )
            )
        elif isinstance(d, Function):
            tail_decls.append(
                _analyze_function(
                    d,
                    ctx.struct_map,
                    ctx.type_mapper,
                    ctx.register_passable_by_decl_id,
                    ret_callback_alias_name=ctx.callback_info.fn_ret_aliases.get(d.decl_id),
                    param_callback_alias_names=tuple(
                        ctx.callback_info.fn_param_aliases.get((d.decl_id, i))
                        for i in range(len(d.params))
                    ),
                )
            )
        elif isinstance(d, GlobalVar):
            tail_decls.append(
                _analyze_global_var(d, ctx.type_mapper, ctx.callback_info.global_aliases)
            )
        elif isinstance(d, (Enum, Const, MacroDecl)):
            tail_decls.append(d)

    needs_global_symbol_helpers = any(
        isinstance(d, AnalyzedGlobalVar) and d.kind == "wrapper" for d in tail_decls
    )

    ctx.type_mapper.warm_ffi_scalar_imports_from_unit(unit)
    ffi_scalar_import_names = ctx.type_mapper.ffi_scalar_import_names

    return AnalyzedUnit(
        unit=unit,
        opts=ctx.options,
        needs_opaque_imports=ctx.import_needs.opaque,
        needs_simd_import=ctx.import_needs.simd,
        needs_complex_import=ctx.import_needs.complex,
        needs_atomic_import=ctx.import_needs.atomic,
        needs_global_symbol_helpers=needs_global_symbol_helpers,
        semantic_fallback_notes=ctx.semantic_fallback_notes,
        unsafe_union_names=ctx.unsafe_union_names,
        emitted_typedef_mojo_names=ctx.emitted_typedef_names,
        callback_aliases=ctx.callback_info.aliases,
        callback_signature_names=ctx.callback_info.signature_names,
        global_callback_aliases=ctx.callback_info.global_aliases,
        ordered_incomplete_structs=ordered_incomplete_structs,
        ordered_structs=ordered_structs,
        unions=unions,
        tail_decls=tuple(tail_decls),
        ffi_scalar_import_names=ffi_scalar_import_names,
    )


def analyzed_struct_for_test(
    decl: Struct,
    *,
    struct_by_name: dict[str, Struct],
) -> AnalyzedStruct:
    reg = build_register_passable_map(struct_by_name).get(decl.decl_id, False)
    return _analyze_struct(decl, struct_by_name, None, register_passable=reg)


def analyze_unit(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    """Run the IR pass pipeline and final semantic analysis over ``unit``."""
    from mojo_bindgen.passes.pipeline import run_ir_passes

    return analyze_unit_semantics(run_ir_passes(unit), options)


class AnalyzeForMojoPass:
    """Produce final Mojo-specific analyzed output from normalized IR."""

    def __init__(self, options: MojoEmitOptions) -> None:
        self._options = options

    def run(self, unit: Unit) -> AnalyzedUnit:
        return analyze_unit_semantics(unit, self._options)
