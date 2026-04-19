"""Unit tests for Mojo type mapping (no libclang)."""

from __future__ import annotations

from mojo_bindgen.codegen.mojo_mapper import map_type
from mojo_bindgen.ir import (
    AtomicType,
    ComplexType,
    FloatKind,
    FloatType,
    IntKind,
    IntType,
    Pointer,
    QualifiedType,
    Qualifiers,
    VectorType,
    VoidType,
)


def test_map_void_pointer_mutable_external() -> None:
    t = Pointer(pointee=None)
    s = map_type(t, ffi_origin="external")
    assert s == "MutOpaquePointer[MutExternalOrigin]"


def test_map_void_pointer_const_external() -> None:
    t = Pointer(pointee=QualifiedType(unqualified=VoidType(), qualifiers=Qualifiers(is_const=True)))
    s = map_type(t, ffi_origin="external")
    assert s == "ImmutOpaquePointer[ImmutExternalOrigin]"


def test_map_void_pointer_mutable_any_origin() -> None:
    t = Pointer(pointee=None)
    s = map_type(t, ffi_origin="any")
    assert s == "MutOpaquePointer[MutAnyOrigin]"


def test_map_const_int_pointer_external() -> None:
    ip = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    t = Pointer(pointee=QualifiedType(unqualified=ip, qualifiers=Qualifiers(is_const=True)))
    s = map_type(t, ffi_origin="external")
    assert s == "UnsafePointer[Int32, ImmutExternalOrigin]"


def test_map_vector_to_simd() -> None:
    f32 = FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4)
    t = VectorType(element=f32, count=4, size_bytes=16)
    assert map_type(t, ffi_origin="external") == "SIMD[DType.float32, 4]"


def test_map_complex_to_complexsimd() -> None:
    f32 = FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4)
    t = ComplexType(element=f32, size_bytes=8)
    assert map_type(t, ffi_origin="external") == "ComplexSIMD[DType.float32, 1]"


def test_map_atomic_to_atomic_dtype() -> None:
    i32 = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    t = AtomicType(value_type=i32)
    assert map_type(t, ffi_origin="external") == "Atomic[DType.int32]"


def test_map_atomic_falls_back_to_underlying_type_when_dtype_missing() -> None:
    wchar = IntType(int_kind=IntKind.WCHAR, size_bytes=4, align_bytes=4)
    t = AtomicType(value_type=wchar)
    assert map_type(t, ffi_origin="external") == "Int32"
