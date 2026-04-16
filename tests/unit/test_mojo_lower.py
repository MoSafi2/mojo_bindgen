"""Unit tests for Mojo type lowering (no libclang)."""

from __future__ import annotations

from mojo_bindgen.ir import IntKind, IntType, Pointer, QualifiedType, Qualifiers, VoidType
from mojo_bindgen.codegen.lowering import lower_type


def test_lower_void_pointer_mutable_external() -> None:
    t = Pointer(pointee=None)
    s = lower_type(t, ffi_origin="external")
    assert s == "MutOpaquePointer[MutExternalOrigin]"


def test_lower_void_pointer_const_external() -> None:
    t = Pointer(pointee=QualifiedType(unqualified=VoidType(), qualifiers=Qualifiers(is_const=True)))
    s = lower_type(t, ffi_origin="external")
    assert s == "ImmutOpaquePointer[ImmutExternalOrigin]"


def test_lower_void_pointer_mutable_any_origin() -> None:
    t = Pointer(pointee=None)
    s = lower_type(t, ffi_origin="any")
    assert s == "MutOpaquePointer[MutAnyOrigin]"


def test_lower_const_int_pointer_external() -> None:
    ip = IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)
    t = Pointer(pointee=QualifiedType(unqualified=ip, qualifiers=Qualifiers(is_const=True)))
    s = lower_type(t, ffi_origin="external")
    assert s == "UnsafePointer[Int32, ImmutExternalOrigin]"
