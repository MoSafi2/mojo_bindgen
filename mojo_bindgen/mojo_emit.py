# mojo_bindgen/mojo_emit.py — emit thin Mojo FFI from bindgen Unit IR.
#
# Typedefs whose name matches an already-emitted struct or enum are skipped
# (see _emit_typedef / emitted_struct_enum_names) to avoid duplicate aliases.
#
# Type lowering policy (canonical vs typedef name)
# ------------------------------------------------
# IR may contain :class:`~mojo_bindgen.ir.TypeRef` (C typedef name + canonical
# type). Use **canonical** lowering everywhere ABI must match layout and FFI
# wire types: struct/union fields, array elements, function-pointer parameter
# and return types inside :class:`~mojo_bindgen.ir.FunctionPtr`, and the type
# lists passed to ``external_call[...]`` / ``OwnedDLHandle.call[...]``.
#
# Use the **typedef name** (as a Mojo identifier) on **top-level function**
# ``def`` signatures — parameters and return type — when a matching
# ``comptime`` typedef alias is emitted in this module, so POSIX-style names
# like ``size_t`` survive in the API surface.
#
# Top-level ``typedef`` declarations use ``canonical`` for the RHS so the alias
# target is a concrete Mojo type (or transparent chain toward one).
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Set
from dataclasses import dataclass
from functools import singledispatchmethod
from typing import Literal

from mojo_bindgen.ir import (
    Array,
    Const,
    EnumRef,
    Enum,
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


_MOJO_MAX_ALIGN_BYTES = 1 << 29
"""Maximum alignment supported by Mojo ``@align`` (per language rules)."""


def _is_power_of_two(n: int) -> bool:
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
        self._lines: list[str] = []
        self._level = 0

    def indent(self) -> None:
        self._level += 1

    def dedent(self) -> None:
        self._level = max(0, self._level - 1)

    def add(self, line: str) -> None:
        self._lines.append("    " * self._level + line)

    def extend(self, lines: list[str]) -> None:
        for ln in lines:
            self.add(ln)

    def render(self) -> str:
        if not self._lines:
            return ""
        return "\n".join(self._lines)


def _peel_typeref(t: Type) -> Type:
    """Unwrap :class:`~mojo_bindgen.ir.TypeRef` to its canonical type."""
    return t.canonical if isinstance(t, TypeRef) else t


def _ffi_origin_names(style: FFIOriginStyle) -> tuple[str, str]:
    """Return (mutable_origin, immutable_origin) for UnsafePointer provenance."""
    if style == "external":
        return ("MutExternalOrigin", "ImmutExternalOrigin")
    return ("MutAnyOrigin", "ImmutAnyOrigin")


class TypeLowerer:
    """Canonical and signature Mojo type lowering from IR :class:`~mojo_bindgen.ir.Type`."""

    def __init__(
        self,
        *,
        ffi_origin: FFIOriginStyle,
        unsafe_union_comptime_names: frozenset[str] | None,
        typedef_mojo_names: frozenset[str] | None = None,
    ) -> None:
        self._ffi_origin = ffi_origin
        self._unsafe_union_comptime_names = unsafe_union_comptime_names
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
        raise TypeError(f"unsupported type: {type(t)!r}")

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
        mut_o, immut_o = _ffi_origin_names(self._ffi_origin)
        if t.pointee is None:
            if t.is_const:
                return f"ImmutOpaquePointer[{immut_o}]"
            return f"MutOpaquePointer[{mut_o}]"
        inner = self.canonical(t.pointee)
        if t.is_const:
            return f"UnsafePointer[{inner}, {immut_o}]"
        return f"UnsafePointer[{inner}, {mut_o}]"

    @canonical.register
    def _(self, t: Array) -> str:
        mut_o, _immut_o = _ffi_origin_names(self._ffi_origin)
        if t.size is None:
            inner = self.canonical(t.element)
            return f"UnsafePointer[{inner}, {mut_o}]"
        inner = self.canonical(t.element)
        return f"InlineArray[{inner}, {t.size}]"

    @canonical.register
    def _(self, t: FunctionPtr) -> str:
        mut_o, _immut_o = _ffi_origin_names(self._ffi_origin)
        return f"MutOpaquePointer[{mut_o}]"

    @canonical.register
    def _(self, t: Opaque) -> str:
        mut_o, _immut_o = _ffi_origin_names(self._ffi_origin)
        return f"MutOpaquePointer[{mut_o}]"

    @canonical.register
    def _(self, t: StructRef) -> str:
        if t.is_union:
            mid = mojo_ident(t.name.strip())
            uq = f"{mid}_Union"
            if self._unsafe_union_comptime_names is not None and uq in self._unsafe_union_comptime_names:
                return uq
            return f"InlineArray[UInt8, {t.size_bytes}]"
        return mojo_ident(t.name.strip())


def lower_type(
    t: Type,
    *,
    ffi_origin: FFIOriginStyle = "external",
    unsafe_union_comptime_names: frozenset[str] | None = None,
) -> str:
    """Lower IR Type to a Mojo type string (ABI / canonical; typedef names erased)."""
    return TypeLowerer(
        ffi_origin=ffi_origin,
        unsafe_union_comptime_names=unsafe_union_comptime_names,
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
        unsafe_union_comptime_names=None,
        typedef_mojo_names=frozenset(),
    )
    for f in decl.fields:
        if not _type_ok_for_unsafe_union_member(f.type):
            return None
        lowered.append(lower.canonical(f.type))
    if len(set(lowered)) != len(lowered):
        return None
    return lowered


def _eligible_unsafe_union_comptime_names(unit: Unit, ffi_origin: FFIOriginStyle) -> frozenset[str]:
    names: set[str] = set()
    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            if _try_unsafe_union_type_list(d, ffi_origin) is not None:
                names.add(f"{mojo_ident(d.name.strip() or d.c_name.strip())}_Union")
    return frozenset(names)


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
    if decl.is_union:
        return False
    return all(_type_ok_for_register_passable_field(f.type, struct_by_name, None) for f in decl.fields)


def _field_mojo_name(f: Field, index: int) -> str:
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


def _function_ptr_comment(
    fp: FunctionPtr,
    *,
    lower: TypeLowerer,
) -> str:
    parts = [lower.canonical(fp.ret)]
    for p in fp.params:
        parts.append(lower.canonical(p))
    var = "varargs" if fp.is_variadic else "fixed"
    return f"function pointer ({var}): ({', '.join(parts)})"


def _struct_dependency_edges(s: Struct) -> list[tuple[str, str]]:
    """Return (successor, predecessor) pairs: `succ` depends on `pred` (emit `pred` first)."""
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
        if isinstance(ty, Pointer) and ty.pointee is not None:
            walk(ty.pointee)
        elif isinstance(ty, Array):
            walk(ty.element)
        elif isinstance(ty, FunctionPtr):
            walk(ty.ret)
            for p in ty.params:
                walk(p)

    for f in s.fields:
        walk(f.type)
    return edges


def _toposort_structs(structs: list[Struct]) -> list[Struct]:
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


@dataclass(frozen=True)
class UnitEmissionPlan:
    """Pure plan for ordering struct and tail declarations."""

    sorted_structs: tuple[Struct, ...]
    emitted_struct_enum_names: frozenset[str]
    tail_decls: tuple[Enum | Typedef | Const | Function, ...]


def _plan_unit_emission(unit: Unit) -> UnitEmissionPlan:
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


def _emit_unsafe_union_comptime(decl: Struct, ffi_origin: FFIOriginStyle) -> str | None:
    """Emit ``comptime name_Union = UnsafeUnion[...]`` or None if not eligible."""
    tl = _try_unsafe_union_type_list(decl, ffi_origin)
    if tl is None:
        return None
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    types_csv = ", ".join(tl)
    return f"comptime {name}_Union = UnsafeUnion[{types_csv}]\n\n"


def _param_names(params: list[Param]) -> list[str]:
    out: list[str] = []
    for i, p in enumerate(params):
        if p.name.strip():
            out.append(mojo_ident(p.name))
        else:
            out.append(f"a{i}")
    return out


def _function_type_param_list(fn: Function, ret_list: str, lower: TypeLowerer) -> str:
    type_params = [f'"{fn.link_name}"', ret_list]
    for p in fn.params:
        type_params.append(lower.canonical(p.type))
    return ", ".join(type_params)


def _emitter_for_struct_emit(
    options: MojoEmitOptions,
    struct_by_name: dict[str, Struct],
    unsafe_union_comptime_names: frozenset[str] | None,
) -> MojoModuleEmitter:
    """Minimal emitter state for isolated struct emission (tests)."""
    emitter = MojoModuleEmitter.__new__(MojoModuleEmitter)
    emitter._opts = options
    emitter._struct_by_name = struct_by_name
    emitter._unsafe_union_comptime_names = unsafe_union_comptime_names
    emitter._typedef_mojo_names = frozenset()
    emitter._types = TypeLowerer(
        ffi_origin=options.ffi_origin,
        unsafe_union_comptime_names=unsafe_union_comptime_names,
        typedef_mojo_names=frozenset(),
    )
    emitter._needs_opaque_imports = False
    return emitter


def _emit_struct(
    decl: Struct,
    options: MojoEmitOptions,
    struct_by_name: dict[str, Struct],
    unsafe_union_comptime_names: frozenset[str] | None,
) -> str:
    """Emit one struct (tests; uses fragment emitter state)."""
    return _emitter_for_struct_emit(options, struct_by_name, unsafe_union_comptime_names)._emit_struct(decl)


class MojoModuleEmitter:
    """Orchestrates prelude, struct ordering, and tail declarations."""

    def __init__(self, unit: Unit, plan: UnitEmissionPlan, options: MojoEmitOptions) -> None:
        self._unit = unit
        self._plan = plan
        self._opts = options
        self._struct_by_name = _struct_by_mojo_name(unit)
        self._typedef_mojo_names = _emitted_typedef_mojo_names(unit, plan)
        self._unsafe_union_comptime_names = _eligible_unsafe_union_comptime_names(unit, options.ffi_origin)
        self._needs_opaque_imports = _unit_needs_opaque_imports(unit)
        self._types = TypeLowerer(
            ffi_origin=options.ffi_origin,
            unsafe_union_comptime_names=self._unsafe_union_comptime_names,
            typedef_mojo_names=self._typedef_mojo_names,
        )

    def emit(self) -> str:
        chunks: list[str] = []
        if self._opts.module_comment:
            chunks.append(self._module_header(self._unit))
        chunks.append(self._import_block())
        chunks.append(self._dl_handle_helpers())
        chunks.append(self._emit_union_comments())
        for s in self._plan.sorted_structs:
            chunks.append(self._emit_struct(s))
        emitted = self._plan.emitted_struct_enum_names
        for d in self._plan.tail_decls:
            chunks.append(self._emit_tail_decl(d, emitted))
        return "".join(chunks)

    def _module_header(self, unit: Unit) -> str:
        return "\n".join(
            [
                "# Generated by mojo_bindgen — do not edit by hand.",
                f"# source: {unit.source_header}",
                f"# library: {unit.library}  link_name: {unit.link_name}",
                f"# FFI mode: {self._opts.linking}",
                "",
            ]
        )

    def _import_block(self) -> str:
        lines: list[str] = []
        if self._opts.linking == "external_call":
            ffi_names = ["external_call"]
            if self._unsafe_union_comptime_names:
                ffi_names.append("UnsafeUnion")
            lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        else:
            ffi_names = ["DEFAULT_RTLD", "OwnedDLHandle"]
            if self._unsafe_union_comptime_names:
                ffi_names.append("UnsafeUnion")
            lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        if self._needs_opaque_imports:
            lines.append("from std.memory import ImmutOpaquePointer, MutOpaquePointer")
        return "\n".join(lines) + "\n\n"

    def _dl_handle_helpers(self) -> str:
        if self._opts.linking != "owned_dl_handle":
            return ""
        if self._opts.library_path_hint:
            path_lit = self._opts.library_path_hint.replace("\\", "\\\\").replace('"', '\\"')
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
        parts: list[str] = []
        fo = self._opts.ffi_origin
        for d in self._unit.decls:
            if isinstance(d, Struct) and d.is_union:
                comptime = _emit_unsafe_union_comptime(d, fo)
                uses = comptime is not None
                if comptime:
                    parts.append(comptime)
                parts.append(self._emit_union_comment(d, uses_unsafe_union=uses))
        return "".join(parts)

    def _emit_union_comment(self, decl: Struct, *, uses_unsafe_union: bool) -> str:
        """Document a C union; struct body is not emitted separately."""
        lower = TypeLowerer(
            ffi_origin=self._opts.ffi_origin,
            unsafe_union_comptime_names=None,
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

    def _emit_field_lines(self, f: Field, index: int, _parent_for_anon: str) -> list[str]:
        type_str = self._types.canonical(f.type)
        fname = _field_mojo_name(f, index)
        lines: list[str] = []
        if f.is_bitfield:
            lines.append(
                f"# bitfield: C bits {f.bit_offset}..{f.bit_offset + f.bit_width - 1} "
                f"({f.bit_width} bits) on {f.type.name}"
            )
        if isinstance(f.type, FunctionPtr):
            lines.append(f"# {_function_ptr_comment(f.type, lower=self._types)}")
        if self._opts.warn_abi and f.is_bitfield:
            lines.append("# ABI: verify bitfield layout matches target C compiler.")
        lines.append(f"var {fname}: {type_str}")
        return lines

    def _emit_struct(self, decl: Struct) -> str:
        name = mojo_ident(decl.name.strip() or decl.c_name.strip())
        traits = (
            "(Copyable, Movable, RegisterPassable)"
            if _struct_decl_register_passable(decl, self._struct_by_name)
            else "(Copyable, Movable)"
        )
        b = CodeBuilder()
        if self._opts.warn_abi:
            b.add(
                f"# struct {decl.c_name} — size={decl.size_bytes} align={decl.align_bytes} "
                "(verify packed/aligned ABI)"
            )
        if self._opts.emit_align:
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
            b.extend(self._emit_field_lines(f, i, name))
        b.dedent()
        b.add("")
        return b.render()

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
        tstr = self._types.canonical(decl.canonical)
        return f"comptime {mojo_ident(decl.name)} = {tstr}\n\n"

    def _emit_const(self, decl: Const) -> str:
        t = lower_primitive(decl.type)
        return f"comptime {mojo_ident(decl.name)} = {t}({decl.value})\n\n"

    def _emit_function_variadic(self, fn: Function, ret_t: str, args_sig: str) -> str:
        c_sig = f"{ret_t} {fn.link_name}({args_sig}, ...)"
        return f"# variadic C function — not callable from thin FFI:\n# {c_sig}\n"

    def _emit_function_non_register_return(self, fn: Function, ret_t: str, args_sig: str) -> str:
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
        bracket_inner = _function_type_param_list(fn, ret_list, self._types)
        name = mojo_ident(fn.name)
        b = CodeBuilder()
        if self._opts.linking == "external_call":
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
        ret_t = self._types.signature(fn.ret)
        params = fn.params
        pnames = _param_names(params)
        arg_decls = [
            f"{pname}: {self._types.signature(p.type)}" for pname, p in zip(pnames, params)
        ]
        args_sig = ", ".join(arg_decls)
        if fn.is_variadic:
            return self._emit_function_variadic(fn, ret_t, args_sig)

        call_args = ", ".join(pnames)
        ret_abi = self._types.canonical(fn.ret)
        is_void = ret_abi == "NoneType"
        ret_list = "NoneType" if is_void else ret_abi

        ret_u = _peel_typeref(fn.ret)
        if isinstance(ret_u, StructRef):
            rs = self._struct_by_name.get(mojo_ident(ret_u.name.strip()))
            if rs is not None and not _struct_decl_register_passable(rs, self._struct_by_name):
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
