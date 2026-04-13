"""IR enrichment and lowering decisions before Mojo string emission.

Pipeline role
-------------
:func:`analyze_unit` is the analysis stage of codegen: it takes a
:class:`~mojo_bindgen.ir.Unit` and options, walks declarations, and returns a
frozen :class:`AnalyzedUnit` consumed by :class:`~mojo_bindgen.mojo_emit.MojoModuleEmitter`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.ir import (
    Array,
    Const,
    Enum,
    EnumRef,
    Field,
    Function,
    FunctionPtr,
    Opaque,
    Primitive,
    Pointer,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    Unit,
)
from mojo_bindgen.codegen.lowering import FFIOriginStyle, TypeLowerer, mojo_ident, peel_typeref
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions

_MOJO_MAX_ALIGN_BYTES = 1 << 29


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def mojo_align_decorator_ok(align_bytes: int) -> bool:
    """Whether ``@align(align_bytes)`` is valid to emit (skip ``@align(1)`` — no extra minimum)."""
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)


def struct_by_mojo_name(unit: Unit) -> dict[str, Struct]:
    """Map Mojo struct alias names to struct declarations (non-union only)."""
    out: dict[str, Struct] = {}
    for d in unit.decls:
        if isinstance(d, Struct) and not d.is_union:
            out[mojo_ident(d.name.strip() or d.c_name.strip())] = d
    return out


def _type_needs_opaque_pointer_import(t: Type) -> bool:
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
    if isinstance(t, Opaque):
        return True
    return False


def unit_needs_opaque_imports(unit: Unit) -> bool:
    """True if any declaration lowers to ``MutOpaquePointer`` / ``ImmutOpaquePointer``."""
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
    return False


def _type_ok_for_unsafe_union_member(t: Type) -> bool:
    u = peel_typeref(t)
    if isinstance(u, TypeRef):
        u = u.canonical
    return isinstance(u, (Primitive, Pointer, FunctionPtr, Opaque))


def _try_unsafe_union_type_list(decl: Struct, ffi_origin: FFIOriginStyle) -> list[str] | None:
    if not decl.is_union or not decl.fields:
        return None
    lowered: list[str] = []
    lower = TypeLowerer(
        ffi_origin=ffi_origin,
        unsafe_union_comptime=None,
        typedef_mojo_names=frozenset(),
    )
    for f in decl.fields:
        if not _type_ok_for_unsafe_union_member(f.type):
            return None
        lowered.append(lower.canonical(f.type))
    if len(set(lowered)) != len(lowered):
        return None
    return lowered


def eligible_unsafe_union_comptime(unit: Unit, ffi_origin: FFIOriginStyle) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            tl = _try_unsafe_union_type_list(d, ffi_origin)
            if tl is not None:
                key = f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union"
                out[key] = tl
    return out


def _type_ok_for_register_passable_field(
    t: Type,
    struct_by_name: dict[str, Struct],
    visiting: set[str] | None = None,
) -> bool:
    if visiting is None:
        visiting = set()
    if isinstance(t, TypeRef):
        return _type_ok_for_register_passable_field(t.canonical, struct_by_name, visiting)
    if isinstance(t, (Primitive, EnumRef, Opaque, FunctionPtr)):
        return True
    if isinstance(t, StructRef):
        mid = mojo_ident(t.name.strip())
        if mid in visiting:
            return False
        s = struct_by_name.get(mid)
        if s is None or s.is_union:
            return False
        visiting.add(mid)
        try:
            return all(
                _type_ok_for_register_passable_field(f.type, struct_by_name, visiting) for f in s.fields
            )
        finally:
            visiting.remove(mid)
    if isinstance(t, Pointer):
        if t.pointee is None:
            return True
        return _type_ok_for_register_passable_field(t.pointee, struct_by_name, visiting)
    if isinstance(t, Array):
        return t.size is None and _type_ok_for_register_passable_field(t.element, struct_by_name, visiting)
    return False


def struct_decl_register_passable(decl: Struct, struct_by_name: dict[str, Struct]) -> bool:
    if decl.is_union:
        return False
    return all(_type_ok_for_register_passable_field(f.type, struct_by_name, None) for f in decl.fields)


def _field_mojo_name(f: Field, index: int) -> str:
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


def _plan_unit_emission(unit: Unit) -> tuple[tuple[Struct, ...], frozenset[str], tuple[Enum | Typedef | Const | Function, ...]]:
    struct_decls = [d for d in unit.decls if isinstance(d, Struct) and not d.is_union]
    emitted_names: set[str] = set()
    for s in struct_decls:
        emitted_names.add(mojo_ident(s.name.strip() or s.c_name.strip()))
    for d in unit.decls:
        if isinstance(d, Enum):
            emitted_names.add(mojo_ident(d.name))
    tail_decls: list[Enum | Typedef | Const | Function] = []
    for d in unit.decls:
        if isinstance(d, (Enum, Typedef, Const, Function)):
            tail_decls.append(d)
    return tuple(struct_decls), frozenset(emitted_names), tuple(tail_decls)


def _emitted_typedef_mojo_names(unit: Unit, emitted_struct_enum_names: frozenset[str]) -> frozenset[str]:
    return frozenset(
        mojo_ident(d.name)
        for d in unit.decls
        if isinstance(d, Typedef) and mojo_ident(d.name) not in emitted_struct_enum_names
    )


@dataclass(frozen=True)
class AnalyzedField:
    """One struct field with precomputed Mojo type string and optional fn-ptr comment."""

    field: Field
    index: int
    mojo_name: str
    canonical_type: str
    fn_ptr_comment: str | None


@dataclass(frozen=True)
class AnalyzedStruct:
    """Non-union struct with layout and passability precomputed."""

    decl: Struct
    register_passable: bool
    align_decorator: int | None
    align_stride_warning: bool
    align_omit_comment: str | None
    fields: tuple[AnalyzedField, ...]


@dataclass(frozen=True)
class AnalyzedTypedef:
    """Typedef with RHS string and whether it duplicates a struct/enum name."""

    decl: Typedef
    skip_duplicate: bool
    mojo_type_rhs: str


FunctionKind = Literal["wrapper", "variadic_stub", "non_register_return_stub"]


@dataclass(frozen=True)
class AnalyzedFunction:
    """C function with precomputed Mojo signature and ``external_call`` bracket payload."""

    decl: Function
    kind: FunctionKind
    ret_t: str
    args_sig: str
    call_args: str
    is_void: bool
    ret_list: str
    bracket_inner: str


@dataclass(frozen=True)
class AnalyzedUnionBlock:
    """Pre-rendered UnsafeUnion comptime (optional) and reference comment block."""

    comptime: str | None
    comment_block: str


TailDecl = Enum | Const | AnalyzedTypedef | AnalyzedFunction


@dataclass(frozen=True)
class AnalyzedUnit:
    """Frozen enrichment of :class:`~mojo_bindgen.ir.Unit` for emission."""

    source_header: str
    library: str
    link_name: str
    opts: MojoEmitOptions
    needs_opaque_imports: bool
    unsafe_union_comptime: dict[str, list[str]] | None
    sorted_structs: tuple[AnalyzedStruct, ...]
    union_blocks: tuple[AnalyzedUnionBlock, ...]
    tail_decls: tuple[TailDecl, ...]


def _build_type_lowerer(
    unit: Unit,
    emitted_struct_enum_names: frozenset[str],
    options: MojoEmitOptions,
) -> tuple[TypeLowerer, dict[str, list[str]] | None]:
    uq = eligible_unsafe_union_comptime(unit, options.ffi_origin)
    td = _emitted_typedef_mojo_names(unit, emitted_struct_enum_names)
    uq_opt: dict[str, list[str]] | None = uq if uq else None
    return (
        TypeLowerer(
            ffi_origin=options.ffi_origin,
            unsafe_union_comptime=uq_opt,
            typedef_mojo_names=td,
        ),
        uq_opt,
    )


def _analyze_struct(
    decl: Struct,
    struct_by_name: dict[str, Struct],
    opts: MojoEmitOptions,
    types: TypeLowerer,
) -> AnalyzedStruct:
    register_passable = struct_decl_register_passable(decl, struct_by_name)
    align_decorator: int | None = None
    align_stride_warning = False
    align_omit_comment: str | None = None
    ab = decl.align_bytes
    if opts.emit_align:
        if mojo_align_decorator_ok(ab):
            align_decorator = ab
            if decl.size_bytes % ab != 0:
                align_stride_warning = True
        elif ab > 1 and not mojo_align_decorator_ok(ab):
            align_omit_comment = (
                f"# @align omitted: C align_bytes={ab} is not a valid Mojo @align (power of 2, max 2**29)."
            )
    analyzed_fields: list[AnalyzedField] = []
    for i, f in enumerate(decl.fields):
        ct = types.canonical(f.type)
        fn_c: str | None = None
        if isinstance(f.type, FunctionPtr):
            fn_c = types.function_ptr_comment(f.type)
        analyzed_fields.append(
            AnalyzedField(
                field=f,
                index=i,
                mojo_name=_field_mojo_name(f, i),
                canonical_type=ct,
                fn_ptr_comment=fn_c,
            )
        )
    return AnalyzedStruct(
        decl=decl,
        register_passable=register_passable,
        align_decorator=align_decorator,
        align_stride_warning=align_stride_warning,
        align_omit_comment=align_omit_comment,
        fields=tuple(analyzed_fields),
    )


def _analyze_function(
    fn: Function,
    struct_by_name: dict[str, Struct],
    types: TypeLowerer,
) -> AnalyzedFunction:
    ret_t = types.signature(fn.ret)
    params = fn.params
    pnames = types.param_names(params)
    arg_decls = [f"{pname}: {types.signature(p.type)}" for pname, p in zip(pnames, params)]
    args_sig = ", ".join(arg_decls)
    if fn.is_variadic:
        return AnalyzedFunction(
            decl=fn,
            kind="variadic_stub",
            ret_t=ret_t,
            args_sig=args_sig,
            call_args="",
            is_void=False,
            ret_list="",
            bracket_inner="",
        )
    call_args = ", ".join(pnames)
    ret_abi = types.canonical(fn.ret)
    is_void = ret_abi == "NoneType"
    ret_list = "NoneType" if is_void else ret_abi
    ret_u = peel_typeref(fn.ret)
    if isinstance(ret_u, StructRef):
        rs = struct_by_name.get(mojo_ident(ret_u.name.strip()))
        if rs is not None and not struct_decl_register_passable(rs, struct_by_name):
            return AnalyzedFunction(
                decl=fn,
                kind="non_register_return_stub",
                ret_t=ret_t,
                args_sig=args_sig,
                call_args=call_args,
                is_void=is_void,
                ret_list=ret_list,
                bracket_inner="",
            )
    bracket_inner = types.function_type_param_list(fn, ret_list)
    return AnalyzedFunction(
        decl=fn,
        kind="wrapper",
        ret_t=ret_t,
        args_sig=args_sig,
        call_args=call_args,
        is_void=is_void,
        ret_list=ret_list,
        bracket_inner=bracket_inner,
    )


def _emit_unsafe_union_comptime_line(decl: Struct, type_list: list[str]) -> str:
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    types_csv = ", ".join(type_list)
    return f"comptime {name}_Union = UnsafeUnion[{types_csv}]\n\n"


def _union_comment_block(
    decl: Struct,
    uses_unsafe_union: bool,
    member_lines: list[tuple[str, str]],
) -> str:
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    if uses_unsafe_union:
        lines = [
            f"# ── C union `{decl.c_name}` — comptime `{name}_Union` = UnsafeUnion[...] (trivial members; see std.ffi).",
            f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
            "# Members (reference only):",
        ]
    else:
        lines = [
            f"# ── C union `{decl.c_name}` — not emitted as a struct.",
            f"# By-value uses InlineArray[UInt8, {decl.size_bytes}] unless you wrap a manual UnsafeUnion (unique trivial members).",
            f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
            "# Members (reference only):",
        ]
    for field_label, tstr in member_lines:
        lines.append(f"#   {field_label}: {tstr}")
    lines.append("")
    return "\n".join(lines)


def analyze_unit(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    """Build an :class:`AnalyzedUnit` from IR: structs, unions, typedefs, and functions.

    Computes struct order, per-field canonical types, union ``UnsafeUnion`` plans,
    typedef skipping for duplicate names, and thin-wrapper vs stub functions.

    Parameters
    ----------
    unit
        Bindgen unit produced from the C AST.
    options
        Controls alignment emission, FFI linking mode, and pointer provenance.

    Returns
    -------
    AnalyzedUnit
        Immutable input for :meth:`mojo_bindgen.mojo_emit.MojoModuleEmitter.emit`.
    """
    sorted_structs_ir, emitted_names, tail_ir = _plan_unit_emission(unit)
    struct_map = struct_by_mojo_name(unit)
    types, uq_opt = _build_type_lowerer(unit, emitted_names, options)

    lower_union_members = TypeLowerer(
        ffi_origin=options.ffi_origin,
        unsafe_union_comptime=None,
        typedef_mojo_names=frozenset(),
    )
    uq = uq_opt or {}

    analyzed_structs = tuple(
        _analyze_struct(s, struct_map, options, types) for s in sorted_structs_ir
    )

    union_blocks: list[AnalyzedUnionBlock] = []
    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            key = f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union"
            tl = uq.get(key)
            comptime: str | None = _emit_unsafe_union_comptime_line(d, tl) if tl is not None else None
            member_lines = [
                (f.name if f.name else "(anonymous)", lower_union_members.canonical(f.type)) for f in d.fields
            ]
            comment = _union_comment_block(d, tl is not None, member_lines)
            union_blocks.append(AnalyzedUnionBlock(comptime=comptime, comment_block=comment))

    tail_out: list[TailDecl] = []
    for d in tail_ir:
        if isinstance(d, Typedef):
            skip = mojo_ident(d.name) in emitted_names
            rhs = types.canonical(d.canonical)
            tail_out.append(AnalyzedTypedef(decl=d, skip_duplicate=skip, mojo_type_rhs=rhs))
        elif isinstance(d, Function):
            tail_out.append(_analyze_function(d, struct_map, types))
        else:
            tail_out.append(d)

    return AnalyzedUnit(
        source_header=unit.source_header,
        library=unit.library,
        link_name=unit.link_name,
        opts=options,
        needs_opaque_imports=unit_needs_opaque_imports(unit),
        unsafe_union_comptime=uq_opt,
        sorted_structs=analyzed_structs,
        union_blocks=tuple(union_blocks),
        tail_decls=tuple(tail_out),
    )


def analyzed_struct_for_test(
    decl: Struct,
    *,
    options: MojoEmitOptions,
    struct_by_name: dict[str, Struct],
    unsafe_union_comptime: dict[str, list[str]] | None,
) -> AnalyzedStruct:
    """Build :class:`AnalyzedStruct` for isolated struct emission (tests)."""
    types = TypeLowerer(
        ffi_origin=options.ffi_origin,
        unsafe_union_comptime=unsafe_union_comptime,
        typedef_mojo_names=frozenset(),
    )
    return _analyze_struct(decl, struct_by_name, options, types)
