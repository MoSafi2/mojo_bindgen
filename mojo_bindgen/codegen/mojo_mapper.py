"""IR → Mojo type strings and identifier mapping (codegen).

Pure conversion shared by analysis and rendering: IR concepts become Mojo-safe
names and type strings. This module does not decide what to emit.
"""

from __future__ import annotations

import json

from mojo_bindgen.ir import (
    AtomicType,
    ComplexType,
    FloatKind,
    FloatType,
    FunctionPtr,
    IntKind,
    IntType,
    QualifiedType,
    Type,
    TypeRef,
    VectorType,
    VoidType,
)


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


def function_ptr_key(fp: FunctionPtr) -> str:
    """Return a stable serialization key for a function-pointer signature."""
    return json.dumps(fp.to_json_dict(), sort_keys=True, separators=(",", ":"))
