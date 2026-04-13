"""Semantic analysis for Mojo code generation.

This module is the middle layer of the codegen stack:

1. parsing produces :class:`~mojo_bindgen.ir.Unit`
2. analysis derives Mojo-specific decisions from that IR
3. rendering turns the analyzed unit into source text

The analysis layer intentionally stores only derived generation decisions.
Facts that are true about the parsed C API remain in the IR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.ir import (
    Array,
    Const,
    GlobalVar,
    Enum,
    EnumRef,
    ComplexType,
    Field,
    Function,
    FunctionPtr,
    OpaqueRecordRef,
    Pointer,
    Primitive,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    UnsupportedType,
    Unit,
    VectorType,
)
from mojo_bindgen.codegen._struct_order import toposort_structs
from mojo_bindgen.codegen.lowering import FFIOriginStyle, TypeLowerer, mojo_ident, peel_typeref
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions

_MOJO_MAX_ALIGN_BYTES = 1 << 29


def _is_power_of_two(n: int) -> bool:
    """Return ``True`` when ``n`` is a positive power-of-two integer."""
    return n > 0 and (n & (n - 1)) == 0


def mojo_align_decorator_ok(align_bytes: int) -> bool:
    """Whether ``@align(align_bytes)`` is valid to emit."""
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map struct declaration ids to non-union struct declarations."""
    out: dict[str, Struct] = {}
    for d in unit.decls:
        if isinstance(d, Struct) and not d.is_union and d.is_complete:
            out[d.decl_id] = d
    return out


def _type_needs_opaque_pointer_import(t: Type) -> bool:
    """Return whether lowering ``t`` requires opaque pointer imports."""
    if isinstance(t, TypeRef):
        return _type_needs_opaque_pointer_import(t.canonical)
    if isinstance(t, EnumRef):
        return False
    if isinstance(t, Pointer):
        if t.pointee is None:
            return True
        return _type_needs_opaque_pointer_import(t.pointee)
    if isinstance(t, Array):
        return _type_needs_opaque_pointer_import(t.element)
    if isinstance(t, FunctionPtr):
        return True
    if isinstance(t, (OpaqueRecordRef, UnsupportedType)):
        return True
    return False


def unit_needs_opaque_imports(unit: Unit) -> bool:
    """True if any declaration lowers to opaque pointer types."""
    for d in unit.decls:
        if isinstance(d, Struct) and not d.is_union:
            for f in d.fields:
                if _type_needs_opaque_pointer_import(f.type):
                    return True
        elif isinstance(d, Function):
            if _type_needs_opaque_pointer_import(d.ret):
                return True
            for p in d.params:
                if _type_needs_opaque_pointer_import(p.type):
                    return True
        elif isinstance(d, Typedef):
            if _type_needs_opaque_pointer_import(d.canonical):
                return True
        elif isinstance(d, GlobalVar):
            if _type_needs_opaque_pointer_import(d.type):
                return True
    return False


def _type_ok_for_unsafe_union_member(t: Type) -> bool:
    """Return whether ``t`` can participate in an emitted ``UnsafeUnion``."""
    u = peel_typeref(t)
    if isinstance(u, TypeRef):
        u = u.canonical
    return isinstance(u, (Primitive, Pointer, FunctionPtr, OpaqueRecordRef))


def _try_unsafe_union_type_list(decl: Struct, ffi_origin: FFIOriginStyle) -> list[str] | None:
    """Return lowered union member types when the union is ``UnsafeUnion``-eligible."""
    if not decl.is_union or not decl.fields:
        return None
    lower = TypeLowerer(
        ffi_origin=ffi_origin,
        unsafe_union_names=frozenset(),
        typedef_mojo_names=frozenset(),
    )
    lowered: list[str] = []
    for f in decl.fields:
        if not _type_ok_for_unsafe_union_member(f.type):
            return None
        lowered.append(lower.canonical(f.type))
    if len(set(lowered)) != len(lowered):
        return None
    return lowered


def eligible_unsafe_union_names(unit: Unit, ffi_origin: FFIOriginStyle) -> frozenset[str]:
    """Return union aliases that can be emitted as ``UnsafeUnion``."""
    out: set[str] = set()
    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            tl = _try_unsafe_union_type_list(d, ffi_origin)
            if tl is not None:
                out.add(f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union")
    return frozenset(out)


def _type_ok_for_register_passable_field(
    t: Type,
    struct_by_id: dict[str, Struct],
    visiting: set[str] | None = None,
) -> bool:
    """Recursively test whether ``t`` is safe to treat as ``RegisterPassable``."""
    if visiting is None:
        visiting = set()
    if isinstance(t, TypeRef):
        return _type_ok_for_register_passable_field(t.canonical, struct_by_id, visiting)
    if isinstance(t, (Primitive, EnumRef, OpaqueRecordRef, FunctionPtr)):
        return True
    if isinstance(t, (UnsupportedType, VectorType, ComplexType)):
        return False
    if isinstance(t, StructRef):
        if t.decl_id in visiting:
            return False
        s = struct_by_id.get(t.decl_id)
        if s is None or s.is_union:
            return False
        visiting.add(t.decl_id)
        try:
            return all(
                _type_ok_for_register_passable_field(f.type, struct_by_id, visiting) for f in s.fields
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


def struct_decl_register_passable(decl: Struct, struct_by_id: dict[str, Struct]) -> bool:
    """Return whether ``decl`` can be emitted with ``RegisterPassable``."""
    if decl.is_union:
        return False
    return all(_type_ok_for_register_passable_field(f.type, struct_by_id, None) for f in decl.fields)


def _field_mojo_name(f: Field, index: int) -> str:
    """Return the emitted Mojo field name, synthesizing one for anonymous fields."""
    if f.source_name:
        return mojo_ident(f.source_name)
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


@dataclass(frozen=True)
class AnalyzedField:
    """Derived field metadata needed by the renderer.

    Attributes
    ----------
    field
        Original IR field declaration.
    index
        Field position within the containing record.
    mojo_name
        Sanitized name used in emitted Mojo source.
    """

    field: Field
    index: int
    mojo_name: str


@dataclass(frozen=True)
class AnalyzedStruct:
    """Derived struct-level emission decisions.

    Attributes
    ----------
    decl
        Original IR struct declaration.
    register_passable
        Whether the emitted struct should conform to ``RegisterPassable``.
    align_decorator
        ``@align`` value to emit, when representable in Mojo.
    align_stride_warning
        Whether the renderer should warn that ``size`` is not a multiple of alignment.
    align_omit_comment
        Optional explanatory comment when C alignment cannot be expressed in Mojo.
    fields
        Per-field derived metadata used during rendering.
    """

    decl: Struct
    register_passable: bool
    align_decorator: int | None
    align_stride_warning: bool
    align_omit_comment: str | None
    fields: tuple[AnalyzedField, ...]


@dataclass(frozen=True)
class AnalyzedTypedef:
    """Derived typedef policy.

    Attributes
    ----------
    decl
        Original IR typedef declaration.
    skip_duplicate
        Whether this typedef is suppressed because a struct or enum already uses the name.
    """

    decl: Typedef
    skip_duplicate: bool


FunctionKind = Literal["wrapper", "variadic_stub", "non_register_return_stub"]


@dataclass(frozen=True)
class AnalyzedFunction:
    """Derived function emission decisions.

    Attributes
    ----------
    decl
        Original IR function declaration.
    kind
        Wrapper strategy selected for the function.
    param_names
        Sanitized parameter names used by the renderer.
    """

    decl: Function
    kind: FunctionKind
    param_names: tuple[str, ...]


@dataclass(frozen=True)
class AnalyzedUnion:
    """Derived union lowering decisions.

    Attributes
    ----------
    decl
        Original IR union declaration.
    uses_unsafe_union
        Whether the union can be emitted as an ``UnsafeUnion`` alias instead of byte storage.
    """

    decl: Struct
    uses_unsafe_union: bool


TailDecl = Enum | Const | GlobalVar | AnalyzedTypedef | AnalyzedFunction


@dataclass(frozen=True)
class AnalyzedUnit:
    """Unit-level semantic analysis for Mojo generation.

    Attributes
    ----------
    unit
        Original parsed IR unit.
    opts
        Codegen options that shaped this analysis.
    needs_opaque_imports
        Whether rendering must import opaque pointer types.
    unsafe_union_names
        Names of union aliases that are emitted as ``UnsafeUnion``.
    emitted_typedef_mojo_names
        Typedef names preserved in top-level emitted signatures.
    ordered_structs
        Struct declarations in emission order, annotated with derived metadata.
    unions
        Union declarations annotated with their lowering strategy.
    tail_decls
        Non-struct declarations in the order they should be rendered.
    """

    unit: Unit
    opts: MojoEmitOptions
    needs_opaque_imports: bool
    unsafe_union_names: frozenset[str]
    emitted_typedef_mojo_names: frozenset[str]
    ordered_structs: tuple[AnalyzedStruct, ...]
    unions: tuple[AnalyzedUnion, ...]
    tail_decls: tuple[TailDecl, ...]


def _ordered_struct_decls(unit: Unit) -> tuple[Struct, ...]:
    """Return non-union structs in dependency-safe emission order."""
    struct_decls = [
        d for d in unit.decls if isinstance(d, Struct) and not d.is_union and d.is_complete
    ]
    return tuple(toposort_structs(struct_decls))


def _emitted_struct_enum_names(unit: Unit, ordered_structs: tuple[Struct, ...]) -> frozenset[str]:
    """Return emitted struct and enum names used to detect typedef collisions."""
    emitted_names: set[str] = set()
    for s in ordered_structs:
        emitted_names.add(mojo_ident(s.name.strip() or s.c_name.strip()))
    for d in unit.decls:
        if isinstance(d, Enum):
            emitted_names.add(mojo_ident(d.name))
    return frozenset(emitted_names)


def _emitted_typedef_mojo_names(unit: Unit, emitted_struct_enum_names: frozenset[str]) -> frozenset[str]:
    """Return typedef names that remain visible on the generated Mojo API surface."""
    return frozenset(
        mojo_ident(d.name)
        for d in unit.decls
        if isinstance(d, Typedef) and mojo_ident(d.name) not in emitted_struct_enum_names
    )


def _analyze_struct(decl: Struct, struct_map: dict[str, Struct], opts: MojoEmitOptions) -> AnalyzedStruct:
    """Analyze one struct declaration and compute rendering decisions for it."""
    register_passable = struct_decl_register_passable(decl, struct_map)
    align_decorator: int | None = None
    align_stride_warning = False
    align_omit_comment: str | None = None
    ab = decl.align_bytes
    if opts.emit_align:
        if mojo_align_decorator_ok(ab):
            align_decorator = ab
            if decl.size_bytes % ab != 0:
                align_stride_warning = True
        elif ab > 1:
            align_omit_comment = (
                f"# @align omitted: C align_bytes={ab} is not a valid Mojo @align (power of 2, max 2**29)."
            )
    if decl.is_packed:
        packed_comment = "# packed record: verify Mojo layout against the target C ABI."
        align_omit_comment = (
            packed_comment if align_omit_comment is None else f"{align_omit_comment} {packed_comment[2:]}"
        )
    fields = tuple(
        AnalyzedField(field=f, index=i, mojo_name=_field_mojo_name(f, i))
        for i, f in enumerate(decl.fields)
    )
    return AnalyzedStruct(
        decl=decl,
        register_passable=register_passable,
        align_decorator=align_decorator,
        align_stride_warning=align_stride_warning,
        align_omit_comment=align_omit_comment,
        fields=fields,
    )


def _analyze_function(
    fn: Function,
    struct_map: dict[str, Struct],
    type_lowerer: TypeLowerer,
) -> AnalyzedFunction:
    """Analyze one function declaration and choose its wrapper strategy."""
    param_names = tuple(type_lowerer.param_names(fn.params))
    if fn.is_variadic:
        return AnalyzedFunction(decl=fn, kind="variadic_stub", param_names=param_names)
    ret_u = peel_typeref(fn.ret)
    if isinstance(ret_u, StructRef):
        rs = struct_map.get(ret_u.decl_id)
        if rs is not None and not struct_decl_register_passable(rs, struct_map):
            return AnalyzedFunction(decl=fn, kind="non_register_return_stub", param_names=param_names)
    return AnalyzedFunction(decl=fn, kind="wrapper", param_names=param_names)


def analyze_unit(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    """Analyze a parsed unit and derive Mojo-specific generation decisions.

    Parameters
    ----------
    unit
        Parsed IR unit produced from the C AST.
    options
        Codegen options that control linking, pointer provenance, warnings, and alignment.

    Returns
    -------
    AnalyzedUnit
        Unit-level semantic analysis consumed by the renderer.
    """
    ordered_struct_decls = _ordered_struct_decls(unit)
    emitted_names = _emitted_struct_enum_names(unit, ordered_struct_decls)
    emitted_typedef_names = _emitted_typedef_mojo_names(unit, emitted_names)
    unsafe_union_names = eligible_unsafe_union_names(unit, options.ffi_origin)
    struct_map = struct_by_decl_id(unit)
    type_lowerer = TypeLowerer(
        ffi_origin=options.ffi_origin,
        unsafe_union_names=unsafe_union_names,
        typedef_mojo_names=emitted_typedef_names,
    )

    ordered_structs = tuple(
        _analyze_struct(decl, struct_map, options) for decl in ordered_struct_decls
    )

    unions = tuple(
        AnalyzedUnion(
            decl=d,
            uses_unsafe_union=f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union" in unsafe_union_names,
        )
        for d in unit.decls
        if isinstance(d, Struct) and d.is_union
    )

    tail_decls: list[TailDecl] = []
    for d in unit.decls:
        if isinstance(d, Typedef):
            tail_decls.append(
                AnalyzedTypedef(decl=d, skip_duplicate=mojo_ident(d.name) in emitted_names)
            )
        elif isinstance(d, Function):
            tail_decls.append(_analyze_function(d, struct_map, type_lowerer))
        elif isinstance(d, (Enum, Const, GlobalVar)):
            tail_decls.append(d)

    return AnalyzedUnit(
        unit=unit,
        opts=options,
        needs_opaque_imports=unit_needs_opaque_imports(unit),
        unsafe_union_names=unsafe_union_names,
        emitted_typedef_mojo_names=emitted_typedef_names,
        ordered_structs=ordered_structs,
        unions=unions,
        tail_decls=tuple(tail_decls),
    )


def analyzed_struct_for_test(
    decl: Struct,
    *,
    options: MojoEmitOptions,
    struct_by_name: dict[str, Struct],
) -> AnalyzedStruct:
    """Build analyzed metadata for a single struct in unit tests.

    This helper keeps isolated struct-rendering tests independent from full
    unit analysis.
    """
    return _analyze_struct(decl, struct_by_name, options)
