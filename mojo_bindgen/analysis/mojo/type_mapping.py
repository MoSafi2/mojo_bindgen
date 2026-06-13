"""Map CIR types into surface-oriented MojoIR type nodes."""

from __future__ import annotations

from dataclasses import dataclass, field

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.ir import (
    _FLOAT_DTYPE_TABLE,
    _INT_DTYPE_TABLE,
    _SIGNED_INT_KINDS,
    _UNSIGNED_INT_KINDS,
    PRIMITIVE_BUILTINS,
    Array,
    AtomicType,
    BuiltinType,
    ComplexType,
    ConstArg,
    DTypeArg,
    EnumRef,
    FloatKind,
    FloatType,
    FunctionPtr,
    IntKind,
    IntType,
    MojoBuiltin,
    NamedType,
    OpaqueRecordRef,
    Param,
    ParametricBase,
    ParametricType,
    Pointer,
    PointerMutability,
    PointerOrigin,
    QualifiedType,
    StructRef,
    Type,
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


def _strip_transparent_wrappers(t: Type) -> Type:
    """Remove wrappers that do not affect surface type structure."""
    while True:
        if isinstance(t, QualifiedType):
            t = t.unqualified
            continue
        break
    return t


def _strip_for_dtype(t: Type) -> Type:
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


def _unwrap_pointer_pointee(t: Type | None) -> tuple[Type | None, PointerMutability]:
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


@dataclass
class MapTypePass:
    """Map CIR types into surface-oriented MojoIR type nodes."""

    _cache: dict[int, Type] = field(default_factory=dict, init=False, repr=False)
    _active: set[int] = field(default_factory=set, init=False, repr=False)
    # ------------------------
    # Entry point
    # ------------------------

    def run(self, t: Type) -> Type:
        key = id(t)
        if key in self._cache:
            return self._cache[key]
        if key in self._active:
            raise TypeMappingError(f"recursive CIR type cycle while mapping {type(t).__name__}")
        self._active.add(key)
        try:
            t_norm = _strip_transparent_wrappers(t)
            result = self._map(t_norm)
        finally:
            self._active.remove(key)

        self._cache[key] = result
        return result

    # ------------------------
    # Core mapping dispatcher
    # ------------------------

    def _map(self, t: Type) -> Type:
        if isinstance(t, (VoidType, IntType, FloatType)):
            return self._map_primitive(t)
        if isinstance(t, AtomicType):
            return self._map_atomic(t)
        if isinstance(t, (TypeRef, EnumRef, StructRef)):
            return self._named(t.name)
        if isinstance(t, OpaqueRecordRef):
            return Pointer(
                pointee=None,
                mutability=PointerMutability.MUT,
                origin=PointerOrigin.EXTERNAL,
            )
        if isinstance(t, Pointer):
            return self._map_pointer(t)
        if isinstance(t, Array):
            return self._map_array(t)
        if isinstance(t, FunctionPtr):
            return self._map_function_ptr(t)
        if isinstance(t, ComplexType):
            return self._map_complex(t)
        if isinstance(t, VectorType):
            return self._map_vector(t)
        if isinstance(t, UnsupportedType):
            return self._unsupported_type(t)
        raise TypeMappingError(f"unsupported CIR type node: {type(t).__name__!r}")

    # ------------------------
    # Named types
    # ------------------------
    def _map_primitive(self, t: PrimitiveCIRType) -> Type:
        if isinstance(t, VoidType):
            key = "void"
        elif isinstance(t, IntType):
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

    def _map_atomic(self, t: AtomicType) -> Type:
        dtype = self._dtype_arg(t.value_type)
        if dtype is not None:
            return ParametricType(
                base=ParametricBase.ATOMIC,
                args=[DTypeArg(dtype)],
            )
        return self.run(t.value_type)

    def _named(self, name: str) -> NamedType:
        return NamedType(name=mojo_ident(name.strip()))

    # ------------------------
    # Pointer mapping
    # ------------------------
    def _map_pointer(self, t: Pointer) -> Pointer:
        pointee, mutability = _unwrap_pointer_pointee(t.pointee)
        if pointee is None or isinstance(pointee, VoidType):
            return Pointer(
                pointee=None,
                mutability=mutability,
                origin=PointerOrigin.EXTERNAL,
                nullable=True,
            )
        return Pointer(
            pointee=self.run(pointee),
            mutability=mutability,
            origin=PointerOrigin.EXTERNAL,
            nullable=True,
        )

    # ------------------------
    # Arrays
    # ------------------------
    def _map_array(self, t: Array) -> Type:
        if t.array_kind == "fixed" and t.size is not None:
            return Array(element=self.run(t.element), size=t.size, array_kind="fixed")

        if t.array_kind == "flexible" and t.size is None:
            # Flexible array members mapped as InlineArray[T, 0]
            return Array(element=self.run(t.element), size=0, array_kind="fixed")
        # fallback: pointer
        return Pointer(
            pointee=self.run(t.element),
            mutability=PointerMutability.MUT,
            origin=PointerOrigin.EXTERNAL,
        )

    # ------------------------
    # Function pointers
    # ------------------------
    def _map_function_ptr(self, t: FunctionPtr) -> FunctionPtr:
        param_names = t.param_names or []
        params = [
            Param(
                name=param_names[i] if i < len(param_names) else "",
                type=self.run(param.type),
            )
            for i, param in enumerate(t.params)
        ]
        return FunctionPtr(
            params=params,
            ret=self.run(t.ret),
            abi="C" if t.calling_convention in (None, "", "c") else t.calling_convention,
            thin=True,
            raises=False,
        )

    # ------------------------
    # Vector & complex
    # ------------------------

    def _map_vector(self, t: VectorType) -> Type:
        if t.count is None:
            return self._opaque_bytes(t.size_bytes)
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(
                base=ParametricBase.SIMD,
                args=[DTypeArg(dtype), ConstArg(t.count)],
            )
        return Array(element=self.run(t.element), size=t.count, array_kind="fixed")

    def _map_complex(self, t: ComplexType) -> Type:
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(
                base=ParametricBase.COMPLEX_SIMD,
                args=[DTypeArg(dtype), ConstArg(1)],
            )

        return Array(element=self.run(t.element), size=2, array_kind="fixed")

    def _unsupported_type(self, t: UnsupportedType) -> Type:
        if t.size_bytes is not None and t.size_bytes > 0:
            return self._opaque_bytes(t.size_bytes)
        return Pointer(
            pointee=None,
            mutability=PointerMutability.MUT,
            origin=PointerOrigin.EXTERNAL,
        )

    def _opaque_bytes(self, size_bytes: int) -> Array:
        return Array(
            element=BuiltinType(name=MojoBuiltin.UINT8), size=size_bytes, array_kind="fixed"
        )

    # ------------------------
    # DType resolution
    # ------------------------

    def _dtype_arg(self, t: Type) -> str | None:
        scalar = self._scalar_for_dtype(t)
        if scalar is None:
            return None
        if isinstance(scalar, IntType):
            return _int_dtype_arg(scalar)
        if isinstance(scalar, FloatType):
            return _FLOAT_DTYPE_TABLE.get(scalar.float_kind)
        return None

    def _scalar_for_dtype(self, t: Type) -> PrimitiveCIRType | None:
        t = _strip_for_dtype(t)
        if isinstance(t, (VoidType, IntType, FloatType)):
            return t
        return None


# ------------------------
# Convenience API
# ------------------------


def map_type(t: Type) -> Type:
    """Map a CIR type to MojoIR."""
    return MapTypePass().run(t)


__all__ = [
    "MapTypePass",
    "TypeMappingError",
    "map_type",
]
