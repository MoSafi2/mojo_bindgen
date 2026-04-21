"""IR → Mojo type strings and identifier mapping (codegen).

Pure conversion shared by analysis and rendering: IR concepts become Mojo-safe
names and type strings. This module does not decide what to emit.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from functools import singledispatchmethod
from typing import Literal

from mojo_bindgen.ir import (
    Array,
    AtomicType,
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
    Qualifiers,
    StructRef,
    Type,
    TypeRef,
    Unit,
    UnsupportedType,
    VectorType,
    VoidType,
)

FFIOriginStyle = Literal["external", "any"]
"""Pointer provenance styles supported by the generated Mojo bindings."""

FFIScalarStyle = Literal["fixed_width", "std_ffi_aliases"]
"""Scalar lowering: fixed-width ints vs ``std.ffi`` ``c_int`` / ``c_long`` / …."""

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


def _dtype_for_width(signed: bool, size_bytes: int) -> str | None:
    if size_bytes == 1:
        return "DType.int8" if signed else "DType.uint8"
    if size_bytes == 2:
        return "DType.int16" if signed else "DType.uint16"
    if size_bytes == 4:
        return "DType.int32" if signed else "DType.uint32"
    if size_bytes == 8:
        return "DType.int64" if signed else "DType.uint64"
    if size_bytes == 16:
        return "DType.int128" if signed else "DType.uint128"
    return None


def map_scalar(t: VoidType | IntType | FloatType) -> str:
    """Map a scalar IR type to its Mojo type name string."""
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


def _std_ffi_int_alias(kind: IntKind) -> str | None:
    """``std.ffi`` comptime name for a C integer family, or None to use fixed-width lowering."""
    return {
        IntKind.CHAR_S: "c_char",
        IntKind.SCHAR: "c_char",
        IntKind.CHAR_U: "c_uchar",
        IntKind.UCHAR: "c_uchar",
        IntKind.SHORT: "c_short",
        IntKind.USHORT: "c_ushort",
        IntKind.INT: "c_int",
        IntKind.UINT: "c_uint",
        IntKind.LONG: "c_long",
        IntKind.ULONG: "c_ulong",
        IntKind.LONGLONG: "c_long_long",
        IntKind.ULONGLONG: "c_ulong_long",
    }.get(kind)


def map_scalar_std_ffi(t: VoidType | IntType | FloatType, imports: set[str]) -> str:
    """Map scalars to ``std.ffi`` aliases; record comptime names in ``imports``."""
    if isinstance(t, VoidType):
        return "NoneType"
    if isinstance(t, IntType):
        if t.int_kind == IntKind.BOOL:
            return "Bool"
        alias = _std_ffi_int_alias(t.int_kind)
        if alias is not None:
            imports.add(alias)
            return alias
        return map_scalar(t)
    if isinstance(t, FloatType):
        if t.float_kind == FloatKind.FLOAT16:
            return "Float16"
        if t.float_kind == FloatKind.FLOAT:
            imports.add("c_float")
            return "c_float"
        if t.float_kind == FloatKind.DOUBLE:
            imports.add("c_double")
            return "c_double"
        return "Float64"
    return "Int32"


def map_scalar_dtype(t: VoidType | IntType | FloatType) -> str | None:
    """Map a scalar IR type to a Mojo ``DType`` constant when representable."""
    if isinstance(t, VoidType):
        return None
    if isinstance(t, IntType):
        if t.int_kind == IntKind.BOOL:
            return "DType.bool"
        if t.int_kind in {
            IntKind.CHAR_S,
            IntKind.SCHAR,
            IntKind.SHORT,
            IntKind.INT,
            IntKind.LONG,
            IntKind.LONGLONG,
            IntKind.INT128,
        }:
            return _dtype_for_width(True, t.size_bytes)
        if t.int_kind in {
            IntKind.CHAR_U,
            IntKind.UCHAR,
            IntKind.USHORT,
            IntKind.UINT,
            IntKind.ULONG,
            IntKind.ULONGLONG,
            IntKind.UINT128,
        }:
            return _dtype_for_width(False, t.size_bytes)
        if t.int_kind == IntKind.CHAR16:
            return "DType.uint16"
        if t.int_kind == IntKind.CHAR32:
            return "DType.uint32"
        return None
    if t.float_kind == FloatKind.FLOAT16:
        return "DType.float16"
    if t.float_kind == FloatKind.FLOAT:
        return "DType.float32"
    if t.float_kind == FloatKind.DOUBLE:
        return "DType.float64"
    return None


def scalar_type_for_dtype(t: Type) -> VoidType | IntType | FloatType | None:
    """Return the scalar core of ``t`` when it has a direct Mojo ``DType`` mapping."""
    core = peel_wrappers(t)
    if isinstance(core, (VoidType, IntType, FloatType)):
        return core
    return None


def map_vector_simd(t: VectorType) -> str | None:
    """Map a representable vector type to ``SIMD[dtype, size]``."""
    element = scalar_type_for_dtype(t.element)
    if element is None or t.count is None:
        return None
    dtype = map_scalar_dtype(element)
    if dtype is None:
        return None
    return f"SIMD[{dtype}, {t.count}]"


def map_complex_simd(t: ComplexType) -> str | None:
    """Map a representable complex scalar to ``ComplexSIMD[dtype, 1]``."""
    dtype = map_scalar_dtype(t.element)
    if dtype is None:
        return None
    return f"ComplexSIMD[{dtype}, 1]"


def map_atomic_type(t: AtomicType) -> str | None:
    """Map a representable atomic scalar to ``Atomic[dtype]``."""
    value = scalar_type_for_dtype(t.value_type)
    if value is None:
        return None
    dtype = map_scalar_dtype(value)
    if dtype is None:
        return None
    return f"Atomic[{dtype}]"


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
    """Mut/Immut origin type names for UnsafePointer / OpaquePointer mapping."""

    mut: str
    immut: str


def pointer_origin_names(style: FFIOriginStyle) -> PointerOriginNames:
    """Return Mut/Immut origin type names for pointer mapping per ``ffi_origin``."""
    if style == "external":
        return PointerOriginNames(mut="MutExternalOrigin", immut="ImmutExternalOrigin")
    return PointerOriginNames(mut="MutAnyOrigin", immut="ImmutAnyOrigin")


def iter_function_ptrs_in_type(t: Type) -> Iterator[FunctionPtr]:
    """Yield every :class:`~mojo_bindgen.ir.FunctionPtr` in ``t``, including nested signatures."""
    while isinstance(t, TypeRef):
        t = t.canonical
    while isinstance(t, QualifiedType):
        t = t.unqualified
    while isinstance(t, AtomicType):
        t = t.value_type

    if isinstance(t, FunctionPtr):
        yield t
        yield from iter_function_ptrs_in_type(t.ret)
        for p in t.params:
            yield from iter_function_ptrs_in_type(p)
        return
    if isinstance(t, Pointer) and t.pointee is not None:
        yield from iter_function_ptrs_in_type(t.pointee)
        return
    if isinstance(t, Array):
        yield from iter_function_ptrs_in_type(t.element)
        return
    if isinstance(t, ComplexType):
        yield from iter_function_ptrs_in_type(t.element)
        return
    if isinstance(t, VectorType):
        yield from iter_function_ptrs_in_type(t.element)
        return


class TypeMapper:
    """Canonical and signature Mojo type mapping from IR :class:`~mojo_bindgen.ir.Type`."""

    def __init__(
        self,
        *,
        ffi_origin: FFIOriginStyle,
        union_alias_names: frozenset[str] | None = None,
        unsafe_union_names: frozenset[str] | None = None,
        typedef_mojo_names: frozenset[str] | None = None,
        callback_signature_names: frozenset[str] | None = None,
        ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases",
    ) -> None:
        """Configure pointer origins, optional ``UnsafeUnion`` names, and typedef aliases for ``signature``."""
        self._ffi_origin = ffi_origin
        self._origin = pointer_origin_names(ffi_origin)
        self._union_alias_names = union_alias_names or frozenset()
        self._unsafe_union_names = unsafe_union_names or frozenset()
        self._typedef_mojo_names = typedef_mojo_names or frozenset()
        self._callback_signature_names = callback_signature_names or frozenset()
        self._ffi_scalar_style = ffi_scalar_style
        self._ffi_scalar_imports: set[str] = set()

    def emit_scalar(self, t: VoidType | IntType | FloatType) -> str:
        """Lower a scalar for emitted Mojo (respects ``ffi_scalar_style``)."""
        return self._map_scalar_emit(t)

    def warm_ffi_scalars_from_function_ptr(self, fp: FunctionPtr) -> None:
        """Record ``std.ffi`` scalars surfaced in callback signatures (matches ``callback_signature_alias_expr``)."""
        self.surface(fp.ret)
        for p in fp.params:
            self.surface(p)

    def _warm_types_for_ffi_imports(self, t: Type) -> None:
        """Canonical lowering plus function-pointer signature surfaces (``canonical`` alone misses FP interiors)."""
        self.canonical(t)
        for fp in iter_function_ptrs_in_type(t):
            self.warm_ffi_scalars_from_function_ptr(fp)

    def warm_ffi_scalar_imports_from_unit(self, unit: Unit) -> None:
        """Pre-resolve all lowered types so ``_ffi_scalar_imports`` is complete before the import line."""
        if self._ffi_scalar_style != "std_ffi_aliases":
            return
        self._ffi_scalar_imports.clear()
        from mojo_bindgen.ir import Const, Enum, GlobalVar, MacroDecl, Struct, Typedef

        for d in unit.decls:
            if isinstance(d, Struct):
                for f in d.fields:
                    self._warm_types_for_ffi_imports(f.type)
            elif isinstance(d, Function):
                self._warm_types_for_ffi_imports(d.ret)
                for p in d.params:
                    self._warm_types_for_ffi_imports(p.type)
            elif isinstance(d, Typedef):
                self._warm_types_for_ffi_imports(d.canonical)
            elif isinstance(d, GlobalVar):
                self._warm_types_for_ffi_imports(d.type)
            elif isinstance(d, Enum):
                self._warm_types_for_ffi_imports(d.underlying)
            elif isinstance(d, Const):
                self._warm_types_for_ffi_imports(d.type)
            elif isinstance(d, MacroDecl) and d.type is not None:
                self._warm_types_for_ffi_imports(d.type)

    @property
    def ffi_scalar_import_names(self) -> frozenset[str]:
        """Comptime ``c_int`` / ``c_long`` / … names needed from ``std.ffi`` for this mapper."""
        return frozenset(self._ffi_scalar_imports)

    def _map_scalar_emit(self, t: VoidType | IntType | FloatType) -> str:
        if self._ffi_scalar_style == "std_ffi_aliases":
            return map_scalar_std_ffi(t, self._ffi_scalar_imports)
        return map_scalar(t)

    def signature(self, t: Type) -> str:
        """
        Map for top-level function ``def`` signatures: typedef alias name when
        this module emits a matching ``comptime`` typedef.
        """
        return self.surface(t)

    def surface(self, t: Type) -> str:
        """Map for public-facing generated API text while preserving emitted typedef aliases."""
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
            mapped = map_complex_simd(t)
            if mapped is not None:
                return mapped
            inner = self.surface(t.element)
            return f"InlineArray[{inner}, 2]"
        if isinstance(t, VectorType):
            mapped = map_vector_simd(t)
            if mapped is not None:
                return mapped
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
        return f'def ({params}) thin abi("C") -> {ret}'

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
        """Map ``t`` to a Mojo type string for ABI/layout (typedef chain resolved)."""
        raise TypeError(
            f"no canonical mapping registered for IR type {type(t).__name__!r}; "
            "extend TypeMapper.canonical with @canonical.register"
        )

    @canonical.register
    def _(self, t: TypeRef) -> str:
        return self.canonical(t.canonical)

    @canonical.register
    def _(self, t: VoidType) -> str:
        return self._map_scalar_emit(t)

    @canonical.register
    def _(self, t: IntType) -> str:
        return self._map_scalar_emit(t)

    @canonical.register
    def _(self, t: FloatType) -> str:
        return self._map_scalar_emit(t)

    @canonical.register
    def _(self, t: QualifiedType) -> str:
        return self.canonical(t.unqualified)

    @canonical.register
    def _(self, t: AtomicType) -> str:
        mapped = map_atomic_type(t)
        if mapped is not None:
            return mapped
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
        mapped = map_complex_simd(t)
        if mapped is not None:
            return mapped
        inner = self.canonical(t.element)
        return f"InlineArray[{inner}, 2]"

    @canonical.register
    def _(self, t: VectorType) -> str:
        mapped = map_vector_simd(t)
        if mapped is not None:
            return mapped
        if t.count is not None:
            inner = self.canonical(t.element)
            return f"InlineArray[{inner}, {t.count}]"
        return f"InlineArray[UInt8, {t.size_bytes}]"

    @canonical.register
    def _(self, t: StructRef) -> str:
        return self._canonical_struct_ref(t)

    @staticmethod
    def _pointer_target(t: Pointer) -> tuple[Type | None, Qualifiers]:
        pointee = t.pointee
        if isinstance(pointee, QualifiedType):
            return pointee.unqualified, pointee.qualifiers
        return pointee, Qualifiers()

    def _canonical_struct_ref(self, t: StructRef) -> str:
        """Map a struct reference, dispatching unions to their storage strategy."""
        if t.is_union:
            return self._canonical_union_struct_ref(t)
        return self._canonical_record_struct_ref(t)

    def _canonical_union_struct_ref(self, t: StructRef) -> str:
        """Map a union reference to its emitted nominal alias or fallback bytes."""
        mid = mojo_ident(t.name.strip())
        if mid in self._union_alias_names:
            return mid
        return f"InlineArray[UInt8, {t.size_bytes}]"

    def _canonical_record_struct_ref(self, t: StructRef) -> str:
        """Map a non-union record reference to its emitted Mojo identifier."""
        return mojo_ident(t.name.strip())

    def function_ptr_canonical_signature_parts(self, fp: FunctionPtr) -> list[str]:
        """Mapped ret and param types (same as used for FFI wire comments)."""
        parts = [self.canonical(fp.ret)]
        parts.extend(self.canonical(p) for p in fp.params)
        return parts

    def function_ptr_surface_signature_parts(self, fp: FunctionPtr) -> list[str]:
        """Typedef-preserving ret and param types for user-facing function-pointer comments."""
        parts = [self.surface(fp.ret)]
        parts.extend(self.surface(p) for p in fp.params)
        return parts

    def function_ptr_canonical_signature(self, fp: FunctionPtr) -> str:
        """Comma-separated mapped ret and param types (semantic signature, not wire pointer type)."""
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
            (
                self.callback_pointer_type(ret_callback_alias_name)
                if ret_callback_alias_name is not None
                else ret_list
            ),
        ]
        for i, p in enumerate(fn.params):
            alias = param_callback_alias_names[i] if i < len(param_callback_alias_names) else None
            # Keep typedef-backed callback signatures (including nested pointer positions)
            # so the callsite argument type exactly matches the wrapper signature.
            type_params.append(
                self.callback_pointer_type(alias) if alias is not None else self.signature(p.type)
            )
        return ", ".join(type_params)


def map_type(
    t: Type,
    *,
    ffi_origin: FFIOriginStyle = "external",
    union_alias_names: frozenset[str] | None = None,
    unsafe_union_names: frozenset[str] | None = None,
    ffi_scalar_style: FFIScalarStyle = "std_ffi_aliases",
) -> str:
    """Map IR Type to a Mojo type string (ABI / canonical; typedef names erased)."""
    return TypeMapper(
        ffi_origin=ffi_origin,
        union_alias_names=union_alias_names,
        unsafe_union_names=unsafe_union_names,
        typedef_mojo_names=frozenset(),
        callback_signature_names=frozenset(),
        ffi_scalar_style=ffi_scalar_style,
    ).canonical(t)


def function_ptr_key(fp: FunctionPtr) -> str:
    """Return a stable serialization key for a function-pointer signature."""
    return json.dumps(fp.to_json_dict(), sort_keys=True, separators=(",", ":"))
