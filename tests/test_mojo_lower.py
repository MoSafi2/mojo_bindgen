"""Unit tests for Mojo type lowering (no libclang)."""

from __future__ import annotations

from mojo_bindgen.ir import Pointer, Primitive, PrimitiveKind
from mojo_bindgen.mojo_emit import lower_type


def test_lower_void_pointer_mutable_external() -> None:
    t = Pointer(pointee=None, is_const=False)
    s = lower_type(t, ffi_origin="external")
    assert s == "MutOpaquePointer[MutExternalOrigin]"


def test_lower_void_pointer_const_external() -> None:
    t = Pointer(pointee=None, is_const=True)
    s = lower_type(t, ffi_origin="external")
    assert s == "ImmutOpaquePointer[ImmutExternalOrigin]"


def test_lower_void_pointer_mutable_any_origin() -> None:
    t = Pointer(pointee=None, is_const=False)
    s = lower_type(t, ffi_origin="any")
    assert s == "MutOpaquePointer[MutAnyOrigin]"


def test_lower_const_int_pointer_external() -> None:
    ip = Primitive(name="int", kind=PrimitiveKind.INT, is_signed=True, size_bytes=4)
    t = Pointer(pointee=ip, is_const=True)
    s = lower_type(t, ffi_origin="external")
    assert s == "UnsafePointer[Int32, ImmutExternalOrigin]"
