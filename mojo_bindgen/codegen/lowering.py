"""IR → Mojo type strings (canonical and typedef-aware signatures).

Used by :mod:`mojo_bindgen.mojo_analyze` (signatures, struct fields) and
:mod:`mojo_bindgen.mojo_emit` (consistent ABI lowering across the pipeline).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import singledispatchmethod
from typing import Literal

from mojo_bindgen.ir import (
    Array,
    EnumRef,
    Function,
    FunctionPtr,
    Opaque,
    Param,
    Pointer,
    Primitive,
    PrimitiveKind,
    StructRef,
    Type,
    TypeRef,
)

FFIOriginStyle = Literal["external", "any"]

# Mojo keywords and reserved — append underscore if collision.
_MOJO_RESERVED = frozenset(
    """
    def struct fn var let inout out mut ref copy owned deinit self Self import from as
    pass return raise raises try except finally with if elif else for while break continue
    and or not is in del alias comptime True False None
    """.split()
)


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


def peel_typeref(t: Type) -> Type:
    """Unwrap :class:`~mojo_bindgen.ir.TypeRef` to its canonical type."""
    return t.canonical if isinstance(t, TypeRef) else t


@dataclass(frozen=True)
class PointerOriginNames:
    """Mut/Immut origin type names for UnsafePointer / OpaquePointer lowering."""

    mut: str
    immut: str


def pointer_origin_names(style: FFIOriginStyle) -> PointerOriginNames:
    """Return Mut/Immut origin type names for pointer lowering per ``ffi_origin``."""
    if style == "external":
        return PointerOriginNames(mut="MutExternalOrigin", immut="ImmutExternalOrigin")
    return PointerOriginNames(mut="MutAnyOrigin", immut="ImmutAnyOrigin")


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
        return self._canonical_struct_ref(t)

    def _canonical_struct_ref(self, t: StructRef) -> str:
        if t.is_union:
            return self._canonical_union_struct_ref(t)
        return self._canonical_record_struct_ref(t)

    def _canonical_union_struct_ref(self, t: StructRef) -> str:
        mid = mojo_ident(t.name.strip())
        uq = f"{mid}_Union"
        if self._unsafe_union_comptime is not None and uq in self._unsafe_union_comptime:
            return uq
        return f"InlineArray[UInt8, {t.size_bytes}]"

    def _canonical_record_struct_ref(self, t: StructRef) -> str:
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
