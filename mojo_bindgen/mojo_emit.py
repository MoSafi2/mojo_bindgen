"""Emit thin Mojo FFI from bindgen Unit IR.

Typedefs whose name matches an already-emitted struct or enum are skipped
(see ``_emit_typedef`` / ``emitted_struct_enum_names``) to avoid duplicate
aliases.

Type lowering policy (canonical vs typedef name)
------------------------------------------------
IR may contain :class:`~mojo_bindgen.ir.TypeRef` (C typedef name + canonical
type). Use **canonical** lowering everywhere ABI must match layout and FFI
wire types: struct/union fields, array elements, function-pointer parameter
and return types inside :class:`~mojo_bindgen.ir.FunctionPtr`, and the type
lists passed to ``external_call[...]`` / ``OwnedDLHandle.call[...]``.

Use the **typedef name** (as a Mojo identifier) on **top-level function**
``def`` signatures — parameters and return type — when a matching
``comptime`` typedef alias is emitted in this module, so POSIX-style names
like ``size_t`` survive in the API surface.

Top-level ``typedef`` declarations use ``canonical`` for the RHS so the alias
target is a concrete Mojo type (or transparent chain toward one).
"""

from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Set
from dataclasses import dataclass
from functools import singledispatchmethod
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
    Param,
    Pointer,
    Primitive,
    PrimitiveKind,
    Struct,
    StructRef,
    Type,
    TypeRef,
    Typedef,
    Unit,
)

LinkingMode = Literal["external_call", "owned_dl_handle"]
FFIOriginStyle = Literal["external", "any"]

# Mojo keywords and reserved — append underscore if collision.
_MOJO_RESERVED = frozenset(
    """
    def struct fn var let inout out mut ref copy owned deinit self Self import from as
    pass return raise raises try except finally with if elif else for while break continue
    and or not is in del alias comptime True False None
    """.split()
)

_MOJO_MAX_ALIGN_BYTES = 1 << 29
"""Maximum alignment supported by Mojo ``@align`` (per language rules)."""


@dataclass(frozen=True)
class PointerOriginNames:
    """Mut/Immut origin type names for UnsafePointer / OpaquePointer lowering."""

    mut: str
    immut: str


@dataclass
class MojoEmitOptions:
    """Controls FFI linking and naming of generated output."""

    linking: LinkingMode = "external_call"
    """external_call: link C symbols at mojo build time; emitted wrappers use ``abi("C")``.
    owned_dl_handle: resolve via ``OwnedDLHandle.call`` (raises); wrappers omit ``abi("C")`` on
    the ``def`` line because ``abi("C")`` combined with ``raises`` currently fails LLVM lowering."""

    library_path_hint: str | None = None
    """If set with owned_dl_handle, pass this path to OwnedDLHandle(...). If None, use DEFAULT_RTLD (symbols must be linked into the process)."""

    module_comment: bool = True
    """Emit a leading comment with source header and library metadata."""

    warn_abi: bool = True
    """Emit comments reminding that packed/aligned layouts need verification."""

    ffi_origin: FFIOriginStyle = "external"
    """Pointer provenance for lowered types: ``external`` → Mut/Immut*ExternalOrigin (recommended for C FFI); ``any`` → *AnyOrigin."""

    emit_align: bool = True
    """If True, emit ``@align(N)`` from C ``Struct.align_bytes`` when valid (Mojo: power of 2, ``N > 1``, max ``2**29``)."""


@dataclass(frozen=True)
class UnitEmissionPlan:
    """Pure plan for ordering struct and tail declarations."""

    sorted_structs: tuple[Struct, ...]
    emitted_struct_enum_names: frozenset[str]
    tail_decls: tuple[Enum | Typedef | Const | Function, ...]


@dataclass(frozen=True)
class EmitContext:
    """Shared state for Mojo emission fragments (structs, functions, imports)."""

    opts: MojoEmitOptions
    types: TypeLowerer
    struct_by_name: dict[str, Struct]
    typedef_mojo_names: frozenset[str]
    unsafe_union_comptime: dict[str, list[str]] | None
    needs_opaque_imports: bool


def pointer_origin_names(style: FFIOriginStyle) -> PointerOriginNames:
    """Return Mut/Immut origin type names for pointer lowering per ``ffi_origin``."""
    if style == "external":
        return PointerOriginNames(mut="MutExternalOrigin", immut="ImmutExternalOrigin")
    return PointerOriginNames(mut="MutAnyOrigin", immut="ImmutAnyOrigin")


def _is_power_of_two(n: int) -> bool:
    """True if ``n`` is a positive power of two."""
    return n > 0 and (n & (n - 1)) == 0


def _mojo_align_decorator_ok(align_bytes: int) -> bool:
    """Whether ``@align(align_bytes)`` is valid to emit (skip ``@align(1)`` — no extra minimum)."""
    if align_bytes <= 1:
        return False
    if align_bytes > _MOJO_MAX_ALIGN_BYTES:
        return False
    return _is_power_of_two(align_bytes)


def mojo_ident(name: str, *, fallback: str = "field") -> str:
    """Map a C identifier to a safe Mojo name."""
    if not name or not name.strip():
        return fallback
    out = []
    for i, ch in enumerate(name):
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out)
    if s and s[0].isdigit():
        s = "_" + s
    if not s:
        s = fallback
    if s in _MOJO_RESERVED:
        s = s + "_"
    return s


def _int_type_for_size(signed: bool, size_bytes: int) -> str:
    """Map integer width in bytes to ``IntN`` / ``UIntN`` (fallback ``Int64``)."""
    if size_bytes == 1:
        return "Int8" if signed else "UInt8"
    if size_bytes == 2:
        return "Int16" if signed else "UInt16"
    if size_bytes == 4:
        return "Int32" if signed else "UInt32"
    if size_bytes == 8:
        return "Int64" if signed else "UInt64"
    if size_bytes == 16:
        return "Int128" if signed else "UInt128"
    return "Int64"  # fallback


def lower_primitive(p: Primitive) -> str:
    """Lower a C primitive to its Mojo type name string."""
    if p.kind == PrimitiveKind.VOID:
        return "NoneType"
    if p.kind == PrimitiveKind.BOOL:
        return "Bool"
    if p.kind == PrimitiveKind.FLOAT:
        if p.size_bytes == 4:
            return "Float32"
        if p.size_bytes == 8:
            return "Float64"
        return "Float64"  # long double / unusual — document via comment at use site
    if p.kind == PrimitiveKind.CHAR:
        # Plain char — treat as Int8 for ABI (signedness varies by platform).
        return "Int8" if p.is_signed else "UInt8"
    if p.kind == PrimitiveKind.INT:
        return _int_type_for_size(p.is_signed, p.size_bytes)
    return "Int32"


class CodeBuilder:
    """Indented line buffer for Mojo source emission."""

    def __init__(self) -> None:
        """Start with an empty buffer at indent level zero."""
        self._lines: list[str] = []
        self._level = 0

    def indent(self) -> None:
        """Increase indentation for subsequent ``add`` / ``extend`` lines."""
        self._level += 1

    def dedent(self) -> None:
        """Decrease indentation (floor at zero)."""
        self._level = max(0, self._level - 1)

    def add(self, line: str) -> None:
        """Append one line with the current indent prefix."""
        self._lines.append("    " * self._level + line)

    def extend(self, lines: list[str]) -> None:
        """Append each line in ``lines`` using the current indent level."""
        for ln in lines:
            self.add(ln)

    def render(self) -> str:
        """Join buffered lines with newlines, or empty string if none."""
        if not self._lines:
            return ""
        return "\n".join(self._lines)


def _peel_typeref(t: Type) -> Type:
    """Unwrap :class:`~mojo_bindgen.ir.TypeRef` to its canonical type."""
    return t.canonical if isinstance(t, TypeRef) else t


class TypeLowerer:
    """Canonical and signature Mojo type lowering from IR :class:`~mojo_bindgen.ir.Type`."""

    def __init__(
        self,
        *,
        ffi_origin: FFIOriginStyle,
        unsafe_union_comptime: dict[str, list[str]] | None,
        typedef_mojo_names: frozenset[str] | None = None,
    ) -> None:
        """Configure pointer origins, optional ``UnsafeUnion`` comptime keys, and typedef aliases for ``signature``."""
        self._ffi_origin = ffi_origin
        self._origin = pointer_origin_names(ffi_origin)
        self._unsafe_union_comptime = unsafe_union_comptime
        self._typedef_mojo_names = typedef_mojo_names or frozenset()

    def signature(self, t: Type) -> str:
        """
        Lower for top-level function ``def`` signatures: typedef alias name when
        this module emits a matching ``comptime`` typedef.
        """
        if isinstance(t, TypeRef):
            mid = mojo_ident(t.name.strip())
            if mid in self._typedef_mojo_names:
                return mid
            return self.canonical(t.canonical)
        return self.canonical(t)

    @singledispatchmethod
    def canonical(self, t: Type) -> str:
        """Lower ``t`` to a Mojo type string for ABI/layout (typedef chain resolved)."""
        raise TypeError(
            f"no canonical lowering registered for IR type {type(t).__name__!r}; "
            "extend TypeLowerer.canonical with @canonical.register"
        )

    @canonical.register
    def _(self, t: TypeRef) -> str:
        return self.canonical(t.canonical)

    @canonical.register
    def _(self, t: Primitive) -> str:
        return lower_primitive(t)

    @canonical.register
    def _(self, t: EnumRef) -> str:
        return mojo_ident(t.name.strip())

    @canonical.register
    def _(self, t: Pointer) -> str:
        o = self._origin
        if t.pointee is None:
            if t.is_const:
                return f"ImmutOpaquePointer[{o.immut}]"
            return f"MutOpaquePointer[{o.mut}]"
        inner = self.canonical(t.pointee)
        if t.is_const:
            return f"UnsafePointer[{inner}, {o.immut}]"
        return f"UnsafePointer[{inner}, {o.mut}]"

    @canonical.register
    def _(self, t: Array) -> str:
        o = self._origin
        if t.size is None:
            inner = self.canonical(t.element)
            return f"UnsafePointer[{inner}, {o.mut}]"
        inner = self.canonical(t.element)
        return f"InlineArray[{inner}, {t.size}]"

    @canonical.register
    def _(self, t: FunctionPtr) -> str:
        return f"MutOpaquePointer[{self._origin.mut}]"

    @canonical.register
    def _(self, t: Opaque) -> str:
        return f"MutOpaquePointer[{self._origin.mut}]"

    @canonical.register
    def _(self, t: StructRef) -> str:
        if t.is_union:
            mid = mojo_ident(t.name.strip())
            uq = f"{mid}_Union"
            if self._unsafe_union_comptime is not None and uq in self._unsafe_union_comptime:
                return uq
            return f"InlineArray[UInt8, {t.size_bytes}]"
        return mojo_ident(t.name.strip())

    def function_ptr_canonical_signature_parts(self, fp: FunctionPtr) -> list[str]:
        """Lowered ret and param types (same as used for FFI wire comments)."""
        parts = [self.canonical(fp.ret)]
        parts.extend(self.canonical(p) for p in fp.params)
        return parts

    def function_ptr_canonical_signature(self, fp: FunctionPtr) -> str:
        """Comma-separated lowered ret and param types (semantic signature, not wire pointer type)."""
        return ", ".join(self.function_ptr_canonical_signature_parts(fp))

    def function_ptr_comment(self, fp: FunctionPtr) -> str:
        """Human-readable comment line for a function-pointer field (fixed vs varargs)."""
        inner = self.function_ptr_canonical_signature(fp)
        var = "varargs" if fp.is_variadic else "fixed"
        return f"function pointer ({var}): ({inner})"

    def param_names(self, params: list[Param]) -> list[str]:
        """Mojo-safe parameter names; unnamed parameters become ``a0``, ``a1``, …."""
        out: list[str] = []
        for i, p in enumerate(params):
            if p.name.strip():
                out.append(mojo_ident(p.name))
            else:
                out.append(f"a{i}")
        return out

    def function_type_param_list(self, fn: Function, ret_list: str) -> str:
        """Comma-separated ``external_call`` / ``OwnedDLHandle.call`` bracket contents (link name, ret, params)."""
        type_params = [f'"{fn.link_name}"', ret_list]
        for p in fn.params:
            type_params.append(self.canonical(p.type))
        return ", ".join(type_params)


def lower_type(
    t: Type,
    *,
    ffi_origin: FFIOriginStyle = "external",
    unsafe_union_comptime: dict[str, list[str]] | None = None,
) -> str:
    """Lower IR Type to a Mojo type string (ABI / canonical; typedef names erased)."""
    return TypeLowerer(
        ffi_origin=ffi_origin,
        unsafe_union_comptime=unsafe_union_comptime,
        typedef_mojo_names=frozenset(),
    ).canonical(t)


def _type_needs_opaque_pointer_import(t: Type) -> bool:
    """Whether lowered type uses ``MutOpaquePointer`` / ``ImmutOpaquePointer`` (imports)."""
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


def _unit_needs_opaque_imports(unit: Unit) -> bool:
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
    """Whether a C union member can appear in ``UnsafeUnion`` (trivial scalars / pointers only)."""
    u = _peel_typeref(t)
    if isinstance(u, TypeRef):
        u = u.canonical
    return isinstance(u, (Primitive, Pointer, FunctionPtr, Opaque))


def _try_unsafe_union_type_list(decl: Struct, ffi_origin: FFIOriginStyle) -> list[str] | None:
    """
    If every field is eligible and lowered types are unique, return Mojo types for ``UnsafeUnion[...]``.
    Otherwise return None (caller uses ``InlineArray[UInt8, N]``).
    """
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


def _eligible_unsafe_union_comptime(unit: Unit, ffi_origin: FFIOriginStyle) -> dict[str, list[str]]:
    """Map ``{mojo_name}_Union`` → lowered member types (computed once per union)."""
    out: dict[str, list[str]] = {}
    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            tl = _try_unsafe_union_type_list(d, ffi_origin)
            if tl is not None:
                key = f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union"
                out[key] = tl
    return out


def _emit_unsafe_union_comptime(decl: Struct, type_list: list[str]) -> str:
    """Emit ``comptime name_Union = UnsafeUnion[...]`` (caller ensures eligibility)."""
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    types_csv = ", ".join(type_list)
    return f"comptime {name}_Union = UnsafeUnion[{types_csv}]\n\n"


def _struct_by_mojo_name(unit: Unit) -> dict[str, Struct]:
    """Map Mojo struct alias names to struct declarations (non-union only)."""
    out: dict[str, Struct] = {}
    for d in unit.decls:
        if isinstance(d, Struct) and not d.is_union:
            out[mojo_ident(d.name.strip() or d.c_name.strip())] = d
    return out


def _type_ok_for_register_passable_field(
    t: Type,
    struct_by_name: dict[str, Struct],
    visiting: set[str] | None = None,
) -> bool:
    """
    Whether a field type can appear on a struct that conforms to RegisterPassable.
    Conservative: fixed-size arrays (InlineArray in Mojo) are excluded.
    """
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


def _struct_decl_register_passable(decl: Struct, struct_by_name: dict[str, Struct]) -> bool:
    """Whether ``decl`` may use the ``RegisterPassable`` trait (all fields eligible)."""
    if decl.is_union:
        return False
    return all(_type_ok_for_register_passable_field(f.type, struct_by_name, None) for f in decl.fields)


def _field_mojo_name(f: Field, index: int) -> str:
    """Mojo field name from IR, or ``_anon_{index}`` for anonymous members."""
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


def _struct_dependency_edges(s: Struct) -> list[tuple[str, str]]:
    """Return (successor, predecessor) pairs: `succ` depends on `pred` (emit `pred` first).

    Only **by-value** struct references create ordering edges. Pointer and function-pointer
    fields do not (C allows pointers to incomplete types); nested struct layout is still
    captured via ``Array``/``StructRef`` for value-embedded arrays of structs.
    """
    me = mojo_ident(s.name.strip() or s.c_name.strip())
    edges: list[tuple[str, str]] = []

    def walk(ty: Type) -> None:
        if isinstance(ty, TypeRef):
            walk(ty.canonical)
            return
        if isinstance(ty, EnumRef):
            return
        if isinstance(ty, StructRef):
            if ty.is_union:
                return
            pred = mojo_ident(ty.name.strip())
            if pred != me:
                edges.append((me, pred))
            return
        if isinstance(ty, Array):
            walk(ty.element)

    for f in s.fields:
        walk(f.type)
    return edges


def _toposort_structs(structs: list[Struct]) -> list[Struct]:
    """Order structs so value-embedded :class:`~mojo_bindgen.ir.StructRef` predecessors come first."""
    if not structs:
        return []

    def name_of(s: Struct) -> str:
        return mojo_ident(s.name.strip() or s.c_name.strip())

    names = [name_of(s) for s in structs]
    known = set(names)
    name_to_struct = {name_of(s): s for s in structs}

    # graph[pred] = successors that must appear after pred
    graph: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {n: 0 for n in names}

    for s in structs:
        succ = name_of(s)
        for succ2, pred in _struct_dependency_edges(s):
            if succ2 != succ:
                continue
            if pred in known and pred != succ:
                if succ not in graph[pred]:
                    graph[pred].add(succ)
                    indegree[succ] += 1

    q = deque(sorted([n for n in names if indegree[n] == 0], key=lambda x: names.index(x)))
    order: list[str] = []
    while q:
        n = q.popleft()
        order.append(n)
        for succ in graph.get(n, ()):
            indegree[succ] -= 1
            if indegree[succ] == 0:
                q.append(succ)

    for n in names:
        if n not in order:
            order.append(n)

    return [name_to_struct[n] for n in order]


def _plan_unit_emission(unit: Unit) -> UnitEmissionPlan:
    """Compute struct order, emitted struct/enum names, and tail declaration list."""
    struct_decls = [d for d in unit.decls if isinstance(d, Struct) and not d.is_union]
    sorted_structs = _toposort_structs(struct_decls)

    emitted_names: set[str] = set()
    for s in sorted_structs:
        emitted_names.add(mojo_ident(s.name.strip() or s.c_name.strip()))

    for d in unit.decls:
        if isinstance(d, Enum):
            emitted_names.add(mojo_ident(d.name))

    tail_decls: list[Enum | Typedef | Const | Function] = []
    for d in unit.decls:
        if isinstance(d, (Enum, Typedef, Const, Function)):
            tail_decls.append(d)

    return UnitEmissionPlan(
        sorted_structs=tuple(sorted_structs),
        emitted_struct_enum_names=frozenset(emitted_names),
        tail_decls=tuple(tail_decls),
    )


def _emitted_typedef_mojo_names(unit: Unit, plan: UnitEmissionPlan) -> frozenset[str]:
    """Mojo names for typedefs that receive a ``comptime`` alias (not skipped by struct/enum duplicate)."""
    emitted = plan.emitted_struct_enum_names
    return frozenset(
        mojo_ident(d.name)
        for d in unit.decls
        if isinstance(d, Typedef) and mojo_ident(d.name) not in emitted
    )


def _emit_context_from_unit(unit: Unit, plan: UnitEmissionPlan, options: MojoEmitOptions) -> EmitContext:
    """Build :class:`EmitContext` (type lowerer, typedef set, opaque-import flag) from ``unit`` and ``plan``."""
    uq = _eligible_unsafe_union_comptime(unit, options.ffi_origin)
    td = _emitted_typedef_mojo_names(unit, plan)
    uq_opt: dict[str, list[str]] | None = uq if uq else None
    return EmitContext(
        opts=options,
        types=TypeLowerer(
            ffi_origin=options.ffi_origin,
            unsafe_union_comptime=uq_opt,
            typedef_mojo_names=td,
        ),
        struct_by_name=_struct_by_mojo_name(unit),
        typedef_mojo_names=td,
        unsafe_union_comptime=uq_opt,
        needs_opaque_imports=_unit_needs_opaque_imports(unit),
    )


def emit_context_for_struct_test(
    options: MojoEmitOptions,
    struct_by_name: dict[str, Struct],
    unsafe_union_comptime: dict[str, list[str]] | None,
) -> EmitContext:
    """Build a minimal :class:`EmitContext` for isolated struct emission (tests)."""
    return EmitContext(
        opts=options,
        types=TypeLowerer(
            ffi_origin=options.ffi_origin,
            unsafe_union_comptime=unsafe_union_comptime,
            typedef_mojo_names=frozenset(),
        ),
        struct_by_name=struct_by_name,
        typedef_mojo_names=frozenset(),
        unsafe_union_comptime=unsafe_union_comptime,
        needs_opaque_imports=False,
    )


def emit_field_lines(ctx: EmitContext, b: CodeBuilder, f: Field, index: int, _parent_for_anon: str) -> None:
    """Emit comments and ``var name: type`` for one struct field (bitfields, fn pointers, ABI hints)."""
    type_str = ctx.types.canonical(f.type)
    fname = _field_mojo_name(f, index)
    if f.is_bitfield:
        b.add(
            f"# bitfield: C bits {f.bit_offset}..{f.bit_offset + f.bit_width - 1} "
            f"({f.bit_width} bits) on {f.type.name}"
        )
    if isinstance(f.type, FunctionPtr):
        b.add(f"# {ctx.types.function_ptr_comment(f.type)}")
    if ctx.opts.warn_abi and f.is_bitfield:
        b.add("# ABI: verify bitfield layout matches target C compiler.")
    b.add(f"var {fname}: {type_str}")


def emit_struct(ctx: EmitContext, decl: Struct) -> str:
    """Emit one non-union ``struct`` definition."""
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    traits = (
        "(Copyable, Movable, RegisterPassable)"
        if _struct_decl_register_passable(decl, ctx.struct_by_name)
        else "(Copyable, Movable)"
    )
    b = CodeBuilder()
    if ctx.opts.warn_abi:
        b.add(
            f"# struct {decl.c_name} — size={decl.size_bytes} align={decl.align_bytes} "
            "(verify packed/aligned ABI)"
        )
    if ctx.opts.emit_align:
        ab = decl.align_bytes
        if _mojo_align_decorator_ok(ab):
            b.add(f"@align({ab})")
            if decl.size_bytes % ab != 0:
                b.add(
                    "# FFI: array stride follows size_of[T](); only T[0] is guaranteed "
                    "align_of[T]-aligned; pad struct size to a multiple of alignment for per-element alignment."
                )
        elif ab > 1 and not _mojo_align_decorator_ok(ab):
            b.add(
                f"# @align omitted: C align_bytes={ab} is not a valid Mojo @align (power of 2, max 2**29)."
            )
    b.add("@fieldwise_init")
    b.add(f"struct {name}{traits}:")
    b.indent()
    for i, f in enumerate(decl.fields):
        emit_field_lines(ctx, b, f, i, name)
    b.dedent()
    b.add("")
    return b.render()


class MojoModuleEmitter:
    """Orchestrates prelude, struct ordering, and tail declarations."""

    def __init__(self, unit: Unit, plan: UnitEmissionPlan, options: MojoEmitOptions) -> None:
        """Prepare emission from ``unit``, a precomputed ``plan``, and ``options``."""
        self._unit = unit
        self._plan = plan
        self._ctx = _emit_context_from_unit(unit, plan, options)

    def emit(self) -> str:
        """Return the full generated Mojo module source."""
        chunks: list[str] = []
        if self._ctx.opts.module_comment:
            chunks.append(self._module_header(self._unit))
        chunks.append(self._import_block())
        chunks.append(self._dl_handle_helpers())
        chunks.append(self._emit_union_comments())
        for s in self._plan.sorted_structs:
            chunks.append(emit_struct(self._ctx, s))
        emitted = self._plan.emitted_struct_enum_names
        for d in self._plan.tail_decls:
            chunks.append(self._emit_tail_decl(d, emitted))
        return "".join(chunks)

    def _module_header(self, unit: Unit) -> str:
        """Leading ``#`` comment: generator notice, source header, library, link name, FFI mode."""
        return "\n".join(
            [
                "# Generated by mojo_bindgen — do not edit by hand.",
                f"# source: {unit.source_header}",
                f"# library: {unit.library}  link_name: {unit.link_name}",
                f"# FFI mode: {self._ctx.opts.linking}",
                "",
            ]
        )

    def _import_block(self) -> str:
        """``std.ffi`` imports for linking mode and optional ``std.memory`` opaque pointer imports."""
        lines: list[str] = []
        if self._ctx.opts.linking == "external_call":
            ffi_names = ["external_call"]
            if self._ctx.unsafe_union_comptime:
                ffi_names.append("UnsafeUnion")
            lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        else:
            ffi_names = ["DEFAULT_RTLD", "OwnedDLHandle"]
            if self._ctx.unsafe_union_comptime:
                ffi_names.append("UnsafeUnion")
            lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        if self._ctx.needs_opaque_imports:
            lines.append("from std.memory import ImmutOpaquePointer, MutOpaquePointer")
        return "\n".join(lines) + "\n\n"

    def _dl_handle_helpers(self) -> str:
        """``comptime`` path and ``_bindgen_dl`` for ``owned_dl_handle`` mode; empty otherwise."""
        if self._ctx.opts.linking != "owned_dl_handle":
            return ""
        if self._ctx.opts.library_path_hint:
            path_lit = self._ctx.opts.library_path_hint.replace("\\", "\\\\").replace('"', '\\"')
            return (
                f'comptime _BINDGEN_LIB_PATH: String = "{path_lit}"\n\n'
                "def _bindgen_dl() raises -> OwnedDLHandle:\n"
                "    return OwnedDLHandle(_BINDGEN_LIB_PATH)\n\n"
            )
        return (
            "# Resolve symbols from libraries already linked into this process (e.g. mojo link step).\n"
            "def _bindgen_dl() raises -> OwnedDLHandle:\n"
            "    return OwnedDLHandle(DEFAULT_RTLD)\n\n"
        )

    def _emit_union_comments(self) -> str:
        """UnsafeUnion comptime aliases and reference comments for each C union in the unit."""
        parts: list[str] = []
        uq = self._ctx.unsafe_union_comptime or {}
        for d in self._unit.decls:
            if isinstance(d, Struct) and d.is_union:
                key = f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union"
                tl = uq.get(key)
                comptime = _emit_unsafe_union_comptime(d, tl) if tl is not None else None
                uses = tl is not None
                if comptime:
                    parts.append(comptime)
                parts.append(self._emit_union_comment(d, uses_unsafe_union=uses))
        return "".join(parts)

    def _emit_union_comment(self, decl: Struct, *, uses_unsafe_union: bool) -> str:
        """Document a C union; struct body is not emitted separately."""
        lower = TypeLowerer(
            ffi_origin=self._ctx.opts.ffi_origin,
            unsafe_union_comptime=None,
            typedef_mojo_names=frozenset(),
        )
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
        for f in decl.fields:
            tstr = lower.canonical(f.type)
            field_label = f.name if f.name else "(anonymous)"
            lines.append(f"#   {field_label}: {tstr}")
        lines.append("")
        return "\n".join(lines)

    def _emit_enum(self, decl: Enum) -> str:
        """Emit C enum as a register-passable struct with `value` + comptime enumerants."""
        base = lower_primitive(decl.underlying)
        name = mojo_ident(decl.name)
        u_spelling = decl.underlying.name
        b = CodeBuilder()
        b.add(f"# enum {decl.c_name} — underlying {u_spelling} → {base} (verify C ABI)")
        b.add("@fieldwise_init")
        b.add(f"struct {name}(Copyable, Movable, RegisterPassable):")
        b.indent()
        b.add(f"var value: {base}")
        for e in decl.enumerants:
            b.add(f"comptime {mojo_ident(e.name)} = Self({base}({e.value}))")
        b.dedent()
        b.add("")
        return b.render()

    def _emit_typedef(self, decl: Typedef, emitted_struct_enum_names: Set[str]) -> str:
        """Emit ``comptime name = …`` unless the typedef name duplicates a struct/enum alias."""
        if mojo_ident(decl.name) in emitted_struct_enum_names:
            return ""
        tstr = self._ctx.types.canonical(decl.canonical)
        return f"comptime {mojo_ident(decl.name)} = {tstr}\n\n"

    def _emit_const(self, decl: Const) -> str:
        """Emit ``comptime name = T(value)`` for a C constant."""
        t = lower_primitive(decl.type)
        return f"comptime {mojo_ident(decl.name)} = {t}({decl.value})\n\n"

    def _emit_function_variadic(self, fn: Function, ret_t: str, args_sig: str) -> str:
        """Comment-only stub: variadic C functions are not wrapped."""
        c_sig = f"{ret_t} {fn.link_name}({args_sig}, ...)"
        return f"# variadic C function — not callable from thin FFI:\n# {c_sig}\n"

    def _emit_function_non_register_return(self, fn: Function, ret_t: str, args_sig: str) -> str:
        """Comment-only stub: non-``RegisterPassable`` struct returns are not wrapped."""
        c_sig = f"{ret_t} {fn.link_name}({args_sig})"
        return (
            "# C return type is not RegisterPassable — external_call cannot model this return; bind manually.\n"
            f"# {c_sig}\n\n"
        )

    def _emit_function_thin_wrapper(
        self,
        fn: Function,
        *,
        ret_t: str,
        args_sig: str,
        call_args: str,
        is_void: bool,
        ret_list: str,
    ) -> str:
        """Emit ``def`` + ``external_call`` or ``OwnedDLHandle.call`` body for one function."""
        bracket_inner = self._ctx.types.function_type_param_list(fn, ret_list)
        name = mojo_ident(fn.name)
        b = CodeBuilder()
        if self._ctx.opts.linking == "external_call":
            if is_void:
                b.add(f'def {name}({args_sig}) abi("C") -> None:')
                b.indent()
                b.add(f"external_call[{bracket_inner}]({call_args})")
            else:
                b.add(f'def {name}({args_sig}) abi("C") -> {ret_t}:')
                b.indent()
                b.add(f"return external_call[{bracket_inner}]({call_args})")
        else:
            # Do not add abi("C") here: combining abi("C") with `raises` on these wrappers
            # triggers an LLVM unrealized_conversion_cast failure in current Mojo (e.g. 0.26.x).
            if is_void:
                b.add(f"def {name}({args_sig}) raises -> None:")
                b.indent()
                b.add(f"_bindgen_dl().call[{bracket_inner}]({call_args})")
            else:
                b.add(f"def {name}({args_sig}) raises -> {ret_t}:")
                b.indent()
                b.add(f"return _bindgen_dl().call[{bracket_inner}]({call_args})")
        b.dedent()
        b.add("")
        return b.render() + "\n"

    def _emit_function(self, fn: Function) -> str:
        """Emit a wrapper, variadic stub, or non-register-return comment for ``fn``."""
        ret_t = self._ctx.types.signature(fn.ret)
        params = fn.params
        pnames = self._ctx.types.param_names(params)
        arg_decls = [
            f"{pname}: {self._ctx.types.signature(p.type)}" for pname, p in zip(pnames, params)
        ]
        args_sig = ", ".join(arg_decls)
        if fn.is_variadic:
            return self._emit_function_variadic(fn, ret_t, args_sig)

        call_args = ", ".join(pnames)
        ret_abi = self._ctx.types.canonical(fn.ret)
        is_void = ret_abi == "NoneType"
        ret_list = "NoneType" if is_void else ret_abi

        ret_u = _peel_typeref(fn.ret)
        if isinstance(ret_u, StructRef):
            rs = self._ctx.struct_by_name.get(mojo_ident(ret_u.name.strip()))
            if rs is not None and not _struct_decl_register_passable(rs, self._ctx.struct_by_name):
                return self._emit_function_non_register_return(fn, ret_t, args_sig)

        return self._emit_function_thin_wrapper(
            fn,
            ret_t=ret_t,
            args_sig=args_sig,
            call_args=call_args,
            is_void=is_void,
            ret_list=ret_list,
        )

    def _emit_tail_decl(self, decl: Enum | Typedef | Const | Function, emitted: frozenset[str]) -> str:
        """Dispatch enum, typedef, const, or function emission (typedefs skip struct/enum name clashes)."""
        if isinstance(decl, Enum):
            return self._emit_enum(decl)
        if isinstance(decl, Typedef):
            return self._emit_typedef(decl, emitted)
        if isinstance(decl, Const):
            return self._emit_const(decl)
        return self._emit_function(decl)


def emit_unit(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Render a Mojo source module as a string."""
    opts = options or MojoEmitOptions()
    plan = _plan_unit_emission(unit)
    return MojoModuleEmitter(unit, plan, opts).emit()
