"""Lower CIR types into surface-oriented MojoIR type nodes."""

from __future__ import annotations

from dataclasses import dataclass, field

from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.ir import (
    _SIGNED_INT_KINDS,
    _UNSIGNED_INT_KINDS,
    Array,
    AtomicType,
    ComplexType,
    EnumRef,
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
    FunctionType,
    MojoBuiltin,
    MojoType,
    NamedType,
    ParametricType,
    PointerMutability,
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
        if isinstance(t, AtomicType):
            t = t.value_type
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
        if isinstance(t, (TypeRef, EnumRef, StructRef)):
            return self._named(t.name)
        if isinstance(t, OpaqueRecordRef):
            return PointerType(pointee=None, mutability=PointerMutability.MUT)
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
            return self._unsupported()
        raise TypeLoweringError(f"unsupported CIR type node: {type(t).__name__!r}")

    # ------------------------
    # Named types
    # ------------------------
    def _lower_primitive(self, t: PrimitiveCIRType) -> BuiltinType:
        if isinstance(t, VoidType):
            key = "void"
        elif isinstance(t, IntType):
            key = t.int_kind
        elif isinstance(t, FloatType):
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

    def _named(self, name: str) -> NamedType:
        return NamedType(name=mojo_ident(name.strip()))

    # ------------------------
    # Pointer lowering
    # ------------------------
    def _lower_pointer(self, t: Pointer) -> PointerType:
        pointee, mutability = _unwrap_pointer_pointee(t.pointee)
        if pointee is None or isinstance(pointee, VoidType):
            return PointerType(pointee=None, mutability=mutability)
        return PointerType(
            pointee=self.run(pointee),
            mutability=mutability,
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
        )

    # ------------------------
    # Function pointers
    # ------------------------
    def _lower_function_ptr(self, t: FunctionPtr) -> PointerType:
        return PointerType(
            pointee=FunctionType(
                params=[self.run(p) for p in t.params],
                ret=self.run(t.ret),
            ),
            mutability=PointerMutability.MUT,
        )

    # ------------------------
    # Vector & complex
    # ------------------------

    def _lower_vector(self, t: VectorType) -> MojoType:
        if t.count is None:
            return self._unsupported()
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(base="SIMD", args=[dtype, str(t.count)])
        return ArrayType(element=self.run(t.element), count=t.count)

    def _lower_complex(self, t: ComplexType) -> MojoType:
        dtype = self._dtype_arg(t.element)
        if dtype is not None:
            return ParametricType(base="ComplexSIMD", args=[dtype, "1"])

        return ArrayType(element=self.run(t.element), count=2)

    def _unsupported(self) -> BuiltinType:
        return BuiltinType(name=MojoBuiltin.UNSUPPORTED)

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
