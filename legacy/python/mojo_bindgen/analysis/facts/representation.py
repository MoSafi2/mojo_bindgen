"""Actual target storage geometry, independently of source layout facts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import assert_never

from mojo_bindgen.ir import (
    BuiltinType,
    ConstArg,
    DTypeArg,
    MojoArray,
    MojoBuiltin,
    MojoFunctionPtr,
    MojoPointer,
    MojoType,
    NamedType,
    OpaqueStorageType,
    ParametricBase,
    ParametricType,
    TypeArg,
)

from .target import TargetQueries


class RepresentationKind(StrEnum):
    VALUE = "value"
    STORAGE = "storage"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class TypeRepresentationFacts:
    kind: RepresentationKind
    layout: tuple[int, int] | None
    reason: str = ""


def storage_type(size: int | None, align: int | None) -> MojoType:
    if (
        size is None
        or align is None
        or size <= 0
        or align <= 0
        or align & (align - 1)
        or align > 2**29
        or size % align
    ):
        return BuiltinType(MojoBuiltin.UNSUPPORTED)
    return OpaqueStorageType(size, align)


def target_layout(t: MojoType, queries: TargetQueries) -> tuple[int, int] | None:
    match t:
        case BuiltinType():
            return queries.builtin_layout(t.name)
        case OpaqueStorageType():
            return (
                (t.size_bytes, t.align_bytes)
                if isinstance(storage_type(t.size_bytes, t.align_bytes), OpaqueStorageType)
                else None
            )
        case NamedType():
            if t.name in ("UInt", "Int"):
                return queries._abi.pointer_size_bytes, queries._abi.pointer_align_bytes
            for prefix in ("UInt", "Int", "Float"):
                if t.name.startswith(prefix) and t.name[len(prefix) :].isdigit():
                    width = int(t.name[len(prefix) :]) // 8
                    if width in (1, 2, 4, 8, 16):
                        return width, 16 if width == 16 else min(
                            width, queries._abi.pointer_align_bytes
                        )
            return None
        case MojoPointer() | MojoFunctionPtr():
            return queries._abi.pointer_size_bytes, queries._abi.pointer_align_bytes
        case MojoArray():
            element = target_layout(t.element, queries)
            return None if element is None or t.size < 0 else (element[0] * t.size, element[1])
        case ParametricType():
            if t.base == ParametricBase.ATOMIC:
                if len(t.args) != 1 or not isinstance(t.args[0], TypeArg):
                    return None
                return target_layout(t.args[0].type, queries)
            dtype = next((a.value for a in t.args if isinstance(a, DTypeArg)), "")
            count = next((a.value for a in t.args if isinstance(a, ConstArg)), 0)
            if (
                t.base not in (ParametricBase.SIMD, ParametricBase.COMPLEX_SIMD)
                or count <= 0
                or count & (count - 1)
            ):
                return None
            width = 1 if dtype == "DType.bool" else 0
            for n in (8, 16, 32, 64, 128):
                if dtype in (f"DType.int{n}", f"DType.uint{n}", f"DType.float{n}"):
                    width = n // 8
            if not width:
                return None
            size = width * count
            return size * (2 if t.base == ParametricBase.COMPLEX_SIMD else 1), size
    assert_never(t)


def contains_storage(t: MojoType) -> bool:
    match t:
        case OpaqueStorageType():
            return True
        case BuiltinType():
            return t.name == MojoBuiltin.UNSUPPORTED
        case MojoArray():
            return contains_storage(t.element)
        case ParametricType():
            return any(contains_storage(a.type) for a in t.args if isinstance(a, TypeArg))
        case NamedType() | MojoPointer() | MojoFunctionPtr():
            return False
    assert_never(t)
