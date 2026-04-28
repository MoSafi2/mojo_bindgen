"""Lower CIR types into surface-oriented MojoIR type nodes."""

from __future__ import annotations

from dataclasses import dataclass, field

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.ir import (
    _SIGNED_INT_KINDS,
    _UNSIGNED_INT_KINDS,
    Array,
    AtomicType,
    ComplexType,
    EnumRef,
    FloatKind,
    FloatType,
    FunctionPtr,
    IntKind,
    IntType,
    OpaqueRecordRef,
    Pointer,
    QualifiedType,
    StructRef,
    Type,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)
from mojo_bindgen.mojo_ir import (
    _FLOAT_DTYPE_TABLE,
    _INT_DTYPE_TABLE,
    PRIMITIVE_BUILTINS,
    ArrayType,
    BuiltinType,
    CallbackParam,
    CallbackType,
    ConstArg,
    DTypeArg,
    MojoBuiltin,
    MojoType,
    NamedType,
    ParametricBase,
    ParametricType,
    PointerMutability,
    PointerOrigin,
    PointerType,
)


class TypeLoweringError(ValueError):
    """Raised when a CIR type cannot be lowered to a MojoIR type."""


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
}


def exact_width_stdint_alias_type(name: str) -> NamedType | None:
    """Return the Mojo fixed-width type for exact-width stdint typedef aliases."""
    mojo_name = _EXACT_WIDTH_STDINT_ALIASES.get(name)
    if mojo_name is None:
        return None
    return NamedType(name=mojo_name)


@dataclass
class LowerTypePass:
    """Lower CIR types into surface-oriented MojoIR type nodes."""

    _cache: dict[int, MojoType] = field(default_factory=dict, init=False, repr=False)
    _active: set[int] = field(default_factory=set, init=False, repr=False)
    # ------------------------
    # Entry point
    # ------------------------

    def run(self, t: Type) -> MojoType:
        key = id(t)
        if key in self._cache:
            return self._cache[key]
        if key in self._active:
            raise TypeLoweringError(f"recursive CIR type cycle while lowering {type(t).__name__}")
        self._active.add(key)
        try:
            t_norm = _strip_transparent_wrappers(t)
            result = self._lower(t_norm)
        finally:
            self._active.remove(key)

        self._cache[key] = result
        return result

    # ------------------------
    # Core lowering dispatcher
    # ------------------------

    def _lower(self, t: Type) -> MojoType:
        if isinstance(t, (VoidType, IntType, FloatType)):
            return self._lower_primitive(t)
        if isinstance(t, AtomicType):
            return self._lower_atomic(t)
        if isinstance(t, (TypeRef, EnumRef, StructRef)):
            return self._named(t.name)
        if isinstance(t, OpaqueRecordRef):
            return PointerType(
                pointee=None,
                mutability=PointerMutability.MUT,
                origin=PointerOrigin.EXTERNAL,
            )
        if isinstance(t, Pointer):
            return self._lower_pointer(t)
        if isinstance(t, Array):
            return self._lower_array(t)
        if isinstance(t, FunctionPtr):
            return self._lower_function_ptr(t)
        if isinstance(t, ComplexType):
            return self._lower_complex(t)
        if isinstance(t, VectorType):
            return self._lower_vector(t)
        if isinstance(t, UnsupportedType):
            return self._unsupported_type(t)
        raise TypeLoweringError(f"unsupported CIR type node: {type(t).__name__!r}")

    # ------------------------
    # Named types
    # ------------------------
    def _lower_primitive(self, t: PrimitiveCIRType) -> MojoType:
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
            raise TypeLoweringError(f"expected CIR primitive type, got {type(t).__name__!r}")

        try:
            builtin = PRIMITIVE_BUILTINS[key]
        except KeyError as exc:
            raise TypeLoweringError(
                f"no Mojo primitive builtin registered for {type(t).__name__} key {key!r}"
            ) from exc
        return BuiltinType(name=builtin)

    def _lower_atomic(self, t: AtomicType) -> MojoType:
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
    # Pointer lowering
    # ------------------------
    def _lower_pointer(self, t: Pointer) -> PointerType:
        pointee, mutability = _unwrap_pointer_pointee(t.pointee)
        if pointee is None or isinstance(pointee, VoidType):
            return PointerType(
                pointee=None,
                mutability=mutability,
                origin=PointerOrigin.EXTERNAL,
            )
        return PointerType(
            pointee=self.run(pointee),
            mutability=mutability,
            origin=PointerOrigin.EXTERNAL,
        )

    # ------------------------
    # Arrays
    # ------------------------
    def _lower_array(self, t: Array) -> MojoType:
        if t.array_kind == "fixed" and t.size is not None:
            return ArrayType(element=self.run(t.element), count=t.size)
        # fallback: pointer
        return PointerType(
            pointee=self.run(t.element),
            mutability=PointerMutability.MUT,
            origin=PointerOrigin.EXTERNAL,
        )

    # ------------------------
    # Function pointers
    # ------------------------
    def _lower_function_ptr(self, t: FunctionPtr) -> CallbackType:
        param_names = t.param_names or []
        params = [
            CallbackParam(
                name=param_names[i] if i < len(param_names) else "",
                type=self.run(param),
            )
            for i, param in enumerate(t.params)
        ]
        return CallbackType(
            params=params,
            ret=self.run(t.ret),
            abi="C" if t.calling_convention in (None, "", "c") else t.calling_convention,
            thin=True,
            raises=False,
            mutability=PointerMutability.MUT,
            origin=PointerOrigin.EXTERNAL,
        )

    # ------------------------
    # Vector & complex
    # ------------------------

    def _lower_vector(self, t: VectorType) -> MojoType:
        if t.count is None:
            return self._opaque_bytes(t.size_bytes)
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(
                base=ParametricBase.SIMD,
                args=[DTypeArg(dtype), ConstArg(t.count)],
            )
        return ArrayType(element=self.run(t.element), count=t.count)

    def _lower_complex(self, t: ComplexType) -> MojoType:
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(
                base=ParametricBase.COMPLEX_SIMD,
                args=[DTypeArg(dtype), ConstArg(1)],
            )

        return ArrayType(element=self.run(t.element), count=2)

    def _unsupported_type(self, t: UnsupportedType) -> MojoType:
        if t.size_bytes is not None and t.size_bytes > 0:
            return self._opaque_bytes(t.size_bytes)
        return PointerType(
            pointee=None,
            mutability=PointerMutability.MUT,
            origin=PointerOrigin.EXTERNAL,
        )

    def _opaque_bytes(self, size_bytes: int) -> ArrayType:
        return ArrayType(element=BuiltinType(name=MojoBuiltin.UINT8), count=size_bytes)

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


def lower_type(t: Type) -> MojoType:
    """Lower a CIR type to MojoIR."""
    return LowerTypePass().run(t)


__all__ = [
    "LowerTypePass",
    "TypeLoweringError",
    "lower_type",
]
