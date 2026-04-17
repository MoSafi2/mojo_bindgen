"""IR -> Mojo type strings and identifier lowering helpers.

This module contains pure lowering logic shared by analysis and rendering.
It does not decide what to emit; it only converts IR concepts into the Mojo
names and type strings needed by later stages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import singledispatchmethod
from typing import Literal

from mojo_bindgen.ir import (
    AtomicType,
    Array,
    ComplexType,
    EnumRef,
    FloatKind,
    FloatType,
    Function,
    FunctionPtr,
    IntKind,
    IntType,
    OpaqueRecordRef,
    Param,
    Pointer,
    QualifiedType,
    StructRef,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)

FFIOriginStyle = Literal["external", "any"]
"""Pointer provenance styles supported by the generated Mojo bindings."""

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


def _is_unsigned_int_kind(kind: IntKind) -> bool:
    return kind in {
        IntKind.CHAR_U,
        IntKind.UCHAR,
        IntKind.USHORT,
        IntKind.UINT,
        IntKind.ULONG,
        IntKind.ULONGLONG,
        IntKind.UINT128,
    }


def lower_scalar(t: VoidType | IntType | FloatType) -> str:
    """Lower a scalar IR type to its Mojo type name string."""
    if isinstance(t, VoidType):
        return "NoneType"
    if isinstance(t, IntType) and t.int_kind == IntKind.BOOL:
        return "Bool"
    if isinstance(t, FloatType):
        if t.float_kind == FloatKind.FLOAT16:
            return "Float16"
        if t.float_kind == FloatKind.FLOAT:
            return "Float32"
        if t.float_kind == FloatKind.DOUBLE:
            return "Float64"
        return "Float64"
    if isinstance(t, IntType):
        return _int_type_for_size(not _is_unsigned_int_kind(t.int_kind), t.size_bytes)
    return "Int32"


def peel_typeref(t: Type) -> Type:
    """Unwrap :class:`~mojo_bindgen.ir.TypeRef` to its canonical type."""
    return t.canonical if isinstance(t, TypeRef) else t


def peel_wrappers(t: Type) -> Type:
    """Unwrap typedef, qualifier, and atomic wrappers to their structural core."""
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
        unsafe_union_names: frozenset[str] | None,
        typedef_mojo_names: frozenset[str] | None = None,
        callback_signature_names: frozenset[str] | None = None,
    ) -> None:
        """Configure pointer origins, optional ``UnsafeUnion`` names, and typedef aliases for ``signature``."""
        self._ffi_origin = ffi_origin
        self._origin = pointer_origin_names(ffi_origin)
        self._unsafe_union_names = unsafe_union_names or frozenset()
        self._typedef_mojo_names = typedef_mojo_names or frozenset()
        self._callback_signature_names = callback_signature_names or frozenset()

    def signature(self, t: Type) -> str:
        """
        Lower for top-level function ``def`` signatures: typedef alias name when
        this module emits a matching ``comptime`` typedef.
        """
        return self.surface(t)

    def surface(self, t: Type) -> str:
        """Lower for public-facing generated API text while preserving emitted typedef aliases."""
        if isinstance(t, TypeRef):
            mid = mojo_ident(t.name.strip())
            if mid in self._callback_signature_names:
                return self.callback_pointer_type(mid)
            if mid in self._typedef_mojo_names:
                return mid
            return self.surface(t.canonical)
        if isinstance(t, Pointer):
            return self._surface_pointer(t)
        if isinstance(t, Array):
            return self._surface_array(t)
        if isinstance(t, ComplexType):
            inner = self.surface(t.element)
            return f"InlineArray[{inner}, 2]"
        if isinstance(t, VectorType):
            if t.count is not None:
                inner = self.surface(t.element)
                return f"InlineArray[{inner}, {t.count}]"
            return self.canonical(t)
        if isinstance(t, StructRef):
            return self._canonical_struct_ref(t)
        if isinstance(t, EnumRef):
            return mojo_ident(t.name.strip())
        return self.canonical(t)

    def callback_pointer_type(self, alias_name: str) -> str:
        """Return the stored pointer type used for a generated callback signature alias."""
        return f"UnsafePointer[{alias_name}, {self._origin.mut}]"

    def callback_signature_alias_expr(self, fp: FunctionPtr) -> str | None:
        """Return a Mojo function-signature alias expression for ``fp`` when representable."""
        if fp.is_variadic:
            return None
        if fp.calling_convention is not None:
            cc = fp.calling_convention.lower()
            if cc not in {"c", "cdecl", "default"}:
                return None
        names = list(fp.param_names or ())
        while len(names) < len(fp.params):
            names.append(f"arg{len(names)}")
        params = ", ".join(
            f"{mojo_ident(name, fallback=f'arg{i}')}: {self.surface(param)}"
            for i, (name, param) in enumerate(zip(names, fp.params))
        )
        ret = self.surface(fp.ret)
        return f'def ({params}) abi("C") -> {ret}'

    def _surface_pointer(self, t: Pointer) -> str:
        o = self._origin
        pointee, qualifiers = self._pointer_target(t)
        if pointee is None or isinstance(peel_wrappers(pointee), VoidType):
            if qualifiers.is_const:
                return f"ImmutOpaquePointer[{o.immut}]"
            return f"MutOpaquePointer[{o.mut}]"
        inner = self.surface(pointee)
        if qualifiers.is_const:
            return f"UnsafePointer[{inner}, {o.immut}]"
        return f"UnsafePointer[{inner}, {o.mut}]"

    def _surface_array(self, t: Array) -> str:
        o = self._origin
        if t.array_kind != "fixed" or t.size is None:
            inner = self.surface(t.element)
            return f"UnsafePointer[{inner}, {o.mut}]"
        inner = self.surface(t.element)
        return f"InlineArray[{inner}, {t.size}]"

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
    def _(self, t: VoidType) -> str:
        return lower_scalar(t)

    @canonical.register
    def _(self, t: IntType) -> str:
        return lower_scalar(t)

    @canonical.register
    def _(self, t: FloatType) -> str:
        return lower_scalar(t)

    @canonical.register
    def _(self, t: QualifiedType) -> str:
        return self.canonical(t.unqualified)

    @canonical.register
    def _(self, t: AtomicType) -> str:
        return self.canonical(t.value_type)

    @canonical.register
    def _(self, t: EnumRef) -> str:
        return mojo_ident(t.name.strip())

    @canonical.register
    def _(self, t: Pointer) -> str:
        o = self._origin
        pointee, qualifiers = self._pointer_target(t)
        if pointee is None or isinstance(peel_wrappers(pointee), VoidType):
            if qualifiers.is_const:
                return f"ImmutOpaquePointer[{o.immut}]"
            return f"MutOpaquePointer[{o.mut}]"
        inner = self.canonical(pointee)
        if qualifiers.is_const:
            return f"UnsafePointer[{inner}, {o.immut}]"
        return f"UnsafePointer[{inner}, {o.mut}]"

    @canonical.register
    def _(self, t: Array) -> str:
        o = self._origin
        if t.array_kind != "fixed" or t.size is None:
            inner = self.canonical(t.element)
            return f"UnsafePointer[{inner}, {o.mut}]"
        inner = self.canonical(t.element)
        return f"InlineArray[{inner}, {t.size}]"

    @canonical.register
    def _(self, t: FunctionPtr) -> str:
        return f"MutOpaquePointer[{self._origin.mut}]"

    @canonical.register
    def _(self, t: OpaqueRecordRef) -> str:
        return f"MutOpaquePointer[{self._origin.mut}]"

    @canonical.register
    def _(self, t: UnsupportedType) -> str:
        if t.size_bytes is not None and t.size_bytes > 0:
            return f"InlineArray[UInt8, {t.size_bytes}]"
        return f"MutOpaquePointer[{self._origin.mut}]"

    @canonical.register
    def _(self, t: ComplexType) -> str:
        inner = self.canonical(t.element)
        return f"InlineArray[{inner}, 2]"

    @canonical.register
    def _(self, t: VectorType) -> str:
        if t.count is not None:
            inner = self.canonical(t.element)
            return f"InlineArray[{inner}, {t.count}]"
        return f"InlineArray[UInt8, {t.size_bytes}]"

    @canonical.register
    def _(self, t: StructRef) -> str:
        return self._canonical_struct_ref(t)

    @staticmethod
    def _pointer_target(t: Pointer) -> tuple[Type | None, object]:
        from mojo_bindgen.ir import Qualifiers

        pointee = t.pointee
        if isinstance(pointee, QualifiedType):
            return pointee.unqualified, pointee.qualifiers
        return pointee, Qualifiers()

    def _canonical_struct_ref(self, t: StructRef) -> str:
        """Lower a struct reference, dispatching unions to their storage strategy."""
        if t.is_union:
            return self._canonical_union_struct_ref(t)
        return self._canonical_record_struct_ref(t)

    def _canonical_union_struct_ref(self, t: StructRef) -> str:
        """Lower a union reference to an ``UnsafeUnion`` alias or byte storage."""
        mid = mojo_ident(t.name.strip())
        uq = f"{mid}_Union"
        if uq in self._unsafe_union_names:
            return uq
        return f"InlineArray[UInt8, {t.size_bytes}]"

    def _canonical_record_struct_ref(self, t: StructRef) -> str:
        """Lower a non-union record reference to its emitted Mojo identifier."""
        return mojo_ident(t.name.strip())

    def function_ptr_canonical_signature_parts(self, fp: FunctionPtr) -> list[str]:
        """Lowered ret and param types (same as used for FFI wire comments)."""
        parts = [self.canonical(fp.ret)]
        parts.extend(self.canonical(p) for p in fp.params)
        return parts

    def function_ptr_surface_signature_parts(self, fp: FunctionPtr) -> list[str]:
        """Typedef-preserving ret and param types for user-facing function-pointer comments."""
        parts = [self.surface(fp.ret)]
        parts.extend(self.surface(p) for p in fp.params)
        return parts

    def function_ptr_canonical_signature(self, fp: FunctionPtr) -> str:
        """Comma-separated lowered ret and param types (semantic signature, not wire pointer type)."""
        return ", ".join(self.function_ptr_canonical_signature_parts(fp))

    def function_ptr_comment(self, fp: FunctionPtr) -> str:
        """Human-readable comment line for a function-pointer field (fixed vs varargs)."""
        inner = ", ".join(self.function_ptr_surface_signature_parts(fp))
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

    def function_type_param_list(
        self,
        fn: Function,
        ret_list: str,
        *,
        ret_callback_alias_name: str | None = None,
        param_callback_alias_names: tuple[str | None, ...] = (),
    ) -> str:
        """Comma-separated ``external_call`` / ``OwnedDLHandle.call`` bracket contents (link name, ret, params)."""
        type_params = [
            f'"{fn.link_name}"',
            self.callback_pointer_type(ret_callback_alias_name) if ret_callback_alias_name is not None else ret_list,
        ]
        for i, p in enumerate(fn.params):
            alias = param_callback_alias_names[i] if i < len(param_callback_alias_names) else None
            # Keep typedef-backed callback signatures (including nested pointer positions)
            # so the callsite argument type exactly matches the wrapper signature.
            type_params.append(self.callback_pointer_type(alias) if alias is not None else self.signature(p.type))
        return ", ".join(type_params)


def lower_type(
    t: Type,
    *,
    ffi_origin: FFIOriginStyle = "external",
    unsafe_union_names: frozenset[str] | None = None,
) -> str:
    """Lower IR Type to a Mojo type string (ABI / canonical; typedef names erased)."""
    return TypeLowerer(
        ffi_origin=ffi_origin,
        unsafe_union_names=unsafe_union_names,
        typedef_mojo_names=frozenset(),
        callback_signature_names=frozenset(),
    ).canonical(t)


def function_ptr_key(fp: FunctionPtr) -> str:
    """Return a stable serialization key for a function-pointer signature."""
    return json.dumps(fp.to_json_dict(), sort_keys=True, separators=(",", ":"))
