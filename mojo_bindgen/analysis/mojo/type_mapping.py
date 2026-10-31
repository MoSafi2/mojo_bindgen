"""Map CIR types into surface-oriented MojoIR type nodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.type_walk import validate_type_tree
from mojo_bindgen.ir import (
    _FLOAT_DTYPE_TABLE,
    _INT_DTYPE_TABLE,
    _SIGNED_INT_KINDS,
    _UNSIGNED_INT_KINDS,
    PRIMITIVE_BUILTINS,
    AtomicType,
    BuiltinType,
    CArray,
    CFunctionPtr,
    ComplexType,
    ConstArg,
    CPointer,
    CType,
    DTypeArg,
    EnumRef,
    FloatKind,
    FloatType,
    IntKind,
    IntType,
    MojoArray,
    MojoBuiltin,
    MojoFunctionPtr,
    MojoParam,
    MojoPointer,
    MojoType,
    NamedType,
    OpaqueRecordRef,
    ParametricBase,
    ParametricType,
    PointerMutability,
    PointerOrigin,
    QualifiedType,
    StructRef,
    TypeArg,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)


class TypeMappingError(ValueError):
    """Raised when a CIR type cannot be mapped to a MojoIR type."""


PrimitiveCIRType = VoidType | IntType | FloatType


# ------------------------
# Normalization
# ------------------------


def _strip_transparent_wrappers(t: CType) -> CType:
    """Remove wrappers that do not affect surface type structure."""
    while True:
        if isinstance(t, QualifiedType):
            t = t.unqualified
            continue
        break
    return t


def _strip_for_dtype(t: CType) -> CType:
    """More aggressive normalization for scalar dtype resolution."""
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
        break
    return t


def _unwrap_pointer_pointee(t: CType | None) -> tuple[CType | None, PointerMutability]:
    if t is None:
        return None, PointerMutability.MUT

    if isinstance(t, QualifiedType):
        mut = PointerMutability.IMMUT if t.qualifiers.is_const else PointerMutability.MUT
        return t.unqualified, mut
    return t, PointerMutability.MUT


def _int_dtype_arg(t: IntType) -> str | None:
    if t.int_kind == IntKind.BOOL:
        return "DType.bool"
    if t.int_kind in _SIGNED_INT_KINDS:
        return _INT_DTYPE_TABLE.get((True, t.size_bytes))
    if t.int_kind in _UNSIGNED_INT_KINDS:
        return _INT_DTYPE_TABLE.get((False, t.size_bytes))
    return None


def _fixed_width_int_name(t: IntType) -> str | None:
    if t.int_kind in {IntKind.INT128, IntKind.WCHAR, IntKind.EXT_INT}:
        return {
            1: "Int8",
            2: "Int16",
            4: "Int32",
            8: "Int64",
            16: "Int128",
        }.get(t.size_bytes)
    if t.int_kind in {IntKind.UINT128, IntKind.CHAR16, IntKind.CHAR32}:
        return {
            1: "UInt8",
            2: "UInt16",
            4: "UInt32",
            8: "UInt64",
            16: "UInt128",
        }.get(t.size_bytes)
    return None


_EXACT_WIDTH_STDINT_ALIASES: dict[str, str] = {
    "int8_t": "Int8",
    "uint8_t": "UInt8",
    "int16_t": "Int16",
    "uint16_t": "UInt16",
    "int32_t": "Int32",
    "uint32_t": "UInt32",
    "int64_t": "Int64",
    "uint64_t": "UInt64",
    "size_t": "UInt",
    "ssize_t": "Int",
}


def exact_width_stdint_alias_type(name: str) -> NamedType | None:
    """Return the Mojo type for common stdint and platform-sized typedef aliases."""
    mojo_name = _EXACT_WIDTH_STDINT_ALIASES.get(name)
    if mojo_name is None:
        return None
    return NamedType(name=mojo_name)


def _storage_size(t: CType) -> int | None:
    match t:
        case (
            IntType()
            | FloatType()
            | AtomicType()
            | CPointer()
            | CArray()
            | CFunctionPtr()
            | OpaqueRecordRef()
            | UnsupportedType()
            | ComplexType()
            | VectorType()
            | StructRef()
        ):
            return t.size_bytes
        case EnumRef():
            return None
        case TypeRef():
            return _storage_size(t.canonical)
        case QualifiedType():
            return _storage_size(t.unqualified)
        case VoidType():
            return None
    assert_never(t)


@dataclass(frozen=True)
class MapTypePass:
    """Pure CIR mapping with target queries fixed for this mapping context."""

    queries: TargetQueries

    def run(self, t: CType) -> MojoType:
        validate_type_tree(t)
        return self._map_validated(t)

    def _map_validated(self, t: CType) -> MojoType:
        return self._map(_strip_transparent_wrappers(t))

    # ------------------------
    # Core mapping dispatcher
    # ------------------------

    def _map(self, t: CType) -> MojoType:
        if isinstance(t, QualifiedType):
            return self._map_validated(t.unqualified)
        if isinstance(t, (VoidType, IntType, FloatType)):
            return self._map_primitive(t)
        if isinstance(t, AtomicType):
            return self._map_atomic(t)
        if isinstance(t, (TypeRef, EnumRef, StructRef)):
            return self._named(t.name)
        if isinstance(t, OpaqueRecordRef):
            return MojoPointer(
                pointee=None,
                mutability=PointerMutability.MUT,
                origin=PointerOrigin.EXTERNAL,
            )
        if isinstance(t, CPointer):
            return self._map_pointer(t)
        if isinstance(t, CArray):
            return self._map_array(t)
        if isinstance(t, CFunctionPtr):
            return self._map_function_ptr(t)
        if isinstance(t, ComplexType):
            return self._map_complex(t)
        if isinstance(t, VectorType):
            return self._map_vector(t)
        if isinstance(t, UnsupportedType):
            return self._unsupported_type(t)
        assert_never(t)

    # ------------------------
    # Named types
    # ------------------------
    def _map_primitive(self, t: PrimitiveCIRType) -> MojoType:
        if isinstance(t, VoidType):
            key = "void"
        elif isinstance(t, IntType):
            if t.int_kind in (IntKind.CHAR_S, IntKind.CHAR_U):
                unsigned = self.queries.default_char_is_unsigned()
                if unsigned is not None:
                    if (t.int_kind == IntKind.CHAR_U) == unsigned:
                        return BuiltinType(MojoBuiltin.C_CHAR)
                    return NamedType("UInt8" if t.int_kind == IntKind.CHAR_U else "Int8")
            fixed_width_name = _fixed_width_int_name(t)
            if fixed_width_name == "Int128":
                return BuiltinType(name=MojoBuiltin.INT128)
            if fixed_width_name == "UInt128":
                return BuiltinType(name=MojoBuiltin.UINT128)
            if fixed_width_name is not None:
                return NamedType(name=fixed_width_name)
            key = t.int_kind
        elif isinstance(t, FloatType):
            if t.float_kind == FloatKind.FLOAT128:
                return self._opaque_bytes(t.size_bytes)
            key = t.float_kind
        else:
            raise TypeMappingError(f"expected CIR primitive type, got {type(t).__name__!r}")

        try:
            builtin = PRIMITIVE_BUILTINS[key]
        except KeyError as exc:
            raise TypeMappingError(
                f"no Mojo primitive builtin registered for {type(t).__name__} key {key!r}"
            ) from exc
        return BuiltinType(name=builtin)

    def _map_atomic(self, t: AtomicType) -> MojoType:
        dtype = self._dtype_arg(t.value_type)
        scalar = self._scalar_for_dtype(t.value_type)
        compatible = scalar is not None and (
            (
                t.size_bytes is None
                or t.size_bytes
                == (scalar.size_bytes if isinstance(scalar, (IntType, FloatType)) else None)
            )
            and (
                t.align_bytes is None
                or t.align_bytes
                == (scalar.align_bytes if isinstance(scalar, (IntType, FloatType)) else None)
            )
        )
        if dtype is not None and compatible:
            return ParametricType(
                base=ParametricBase.ATOMIC,
                args=(TypeArg(self._map_validated(t.value_type)),),
            )
        size = t.size_bytes or _storage_size(_strip_for_dtype(t.value_type))
        if size:
            return self._opaque_bytes(size)
        raise TypeMappingError("atomic storage has no representable scalar type or known size")

    def _named(self, name: str) -> NamedType:
        return NamedType(name=mojo_ident(name.strip()))

    # ------------------------
    # Pointer mapping
    # ------------------------
    def _map_pointer(self, t: CPointer) -> MojoPointer:
        pointee, mutability = _unwrap_pointer_pointee(t.pointee)
        if pointee is None or isinstance(pointee, VoidType):
            return MojoPointer(
                pointee=None,
                mutability=mutability,
                origin=PointerOrigin.EXTERNAL,
                nullable=True,
            )
        return MojoPointer(
            pointee=self._map_validated(pointee),
            mutability=mutability,
            origin=PointerOrigin.EXTERNAL,
            nullable=True,
        )

    # ------------------------
    # Arrays
    # ------------------------
    def _map_array(self, t: CArray) -> MojoType:
        if t.array_kind == "fixed" and t.size is not None:
            return MojoArray(element=self._map_validated(t.element), size=t.size)

        if t.array_kind == "flexible" and t.size is None:
            # Flexible array members mapped as Array[T, 0]
            return MojoArray(element=self._map_validated(t.element), size=0)
        # fallback: pointer
        return MojoPointer(
            pointee=self._map_validated(t.element),
            mutability=PointerMutability.MUT,
            origin=PointerOrigin.EXTERNAL,
        )

    # ------------------------
    # Function pointers
    # ------------------------
    def _map_function_ptr(self, t: CFunctionPtr) -> MojoFunctionPtr:
        param_names = t.param_names or ()
        params = [
            MojoParam(
                name=param_names[i] if i < len(param_names) else "",
                type=self._map_validated(param.type),
            )
            for i, param in enumerate(t.params)
        ]
        return MojoFunctionPtr(
            params=tuple(params),
            ret=self._map_validated(t.ret),
            abi="C" if t.calling_convention in (None, "", "c") else t.calling_convention,
            thin=True,
            raises=False,
        )

    # ------------------------
    # Vector & complex
    # ------------------------

    def _map_vector(self, t: VectorType) -> MojoType:
        if t.count is None:
            return self._opaque_bytes(t.size_bytes)
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(
                base=ParametricBase.SIMD,
                args=(DTypeArg(dtype), ConstArg(t.count)),
            )
        return MojoArray(element=self._map_validated(t.element), size=t.count)

    def _map_complex(self, t: ComplexType) -> MojoType:
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(
                base=ParametricBase.COMPLEX_SIMD,
                args=(DTypeArg(dtype), ConstArg(1)),
            )

        return MojoArray(element=self._map_validated(t.element), size=2)

    def _unsupported_type(self, t: UnsupportedType) -> MojoType:
        if t.size_bytes is not None and t.size_bytes > 0:
            return self._opaque_bytes(t.size_bytes)
        return MojoPointer(
            pointee=None,
            mutability=PointerMutability.MUT,
            origin=PointerOrigin.EXTERNAL,
        )

    def _opaque_bytes(self, size_bytes: int) -> MojoArray:
        return MojoArray(element=BuiltinType(name=MojoBuiltin.UINT8), size=size_bytes)

    # ------------------------
    # DType resolution
    # ------------------------

    def _dtype_arg(self, t: CType) -> str | None:
        scalar = self._scalar_for_dtype(t)
        if scalar is None:
            return None
        if isinstance(scalar, IntType):
            return _int_dtype_arg(scalar)
        if isinstance(scalar, FloatType):
            return _FLOAT_DTYPE_TABLE.get(scalar.float_kind)
        return None

    def _scalar_for_dtype(self, t: CType) -> PrimitiveCIRType | None:
        t = _strip_for_dtype(t)
        if isinstance(t, (VoidType, IntType, FloatType)):
            return t
        return None


# ------------------------
# Convenience API
# ------------------------


def map_type(t: CType, *, queries: TargetQueries) -> MojoType:
    """Map a CIR type to MojoIR."""
    return MapTypePass(queries=queries).run(t)


__all__ = [
    "MapTypePass",
    "TypeMappingError",
    "map_type",
]
