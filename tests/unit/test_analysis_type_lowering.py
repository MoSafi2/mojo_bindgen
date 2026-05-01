"""Unit tests for surface-oriented CIR -> MojoIR type lowering."""

from __future__ import annotations

from mojo_bindgen.analysis.type_lowering import LowerTypePass, lower_type
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    ComplexType,
    EnumRef,
    FloatKind,
    FloatType,
    FunctionPtr,
    IntKind,
    IntType,
    Pointer,
    QualifiedType,
    Qualifiers,
    StructRef,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)
from mojo_bindgen.mojo_ir import (
    ArrayType,
    BuiltinType,
    ConstArg,
    DTypeArg,
    FunctionType,
    MojoBuiltin,
    NamedType,
    Param,
    ParametricBase,
    ParametricType,
    PointerMutability,
    PointerType,
)


def test_lower_type_maps_primitives_to_builtins() -> None:
    lowered = lower_type(VoidType())

    assert lowered == BuiltinType(name=MojoBuiltin.NONE)
    assert lower_type(IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)) == BuiltinType(
        name=MojoBuiltin.C_INT
    )


def test_lower_type_preserves_typeref_name_as_named_type() -> None:
    t = TypeRef(
        decl_id="typedef:my_uint",
        name="my_uint",
        canonical=IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4),
    )

    assert lower_type(t) == NamedType(name="my_uint")


def test_lower_type_maps_named_record_and_enum_refs() -> None:
    enum_ref = EnumRef(
        decl_id="enum:mode_t",
        name="mode_t",
        c_name="mode_t",
        underlying=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
    )
    struct_ref = StructRef(
        decl_id="struct:payload_t",
        name=" payload_t ",
        c_name="payload_t",
    )

    assert lower_type(enum_ref) == NamedType(name="mode_t")
    assert lower_type(struct_ref) == NamedType(name="payload_t")


def test_lower_type_uses_pointer_pointee_constness_for_mutability() -> None:
    const_int_ptr = Pointer(
        pointee=QualifiedType(
            unqualified=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
            qualifiers=Qualifiers(is_const=True),
        )
    )
    void_ptr = Pointer(pointee=None)

    assert lower_type(const_int_ptr) == PointerType(
        pointee=BuiltinType(name=MojoBuiltin.C_INT),
        mutability=PointerMutability.IMMUT,
        nullable=True,
    )
    assert lower_type(void_ptr) == PointerType(
        pointee=None,
        mutability=PointerMutability.MUT,
        nullable=True,
    )


def test_lower_type_maps_fixed_arrays_and_pointer_falls_back_for_flexible_arrays() -> None:
    element = IntType(int_kind=IntKind.SHORT, size_bytes=2, align_bytes=2)

    assert lower_type(Array(element=element, size=4, array_kind="fixed")) == ArrayType(
        element=BuiltinType(name=MojoBuiltin.C_SHORT),
        count=4,
    )
    assert lower_type(Array(element=element, size=None, array_kind="flexible")) == PointerType(
        pointee=BuiltinType(name=MojoBuiltin.C_SHORT),
        mutability=PointerMutability.MUT,
    )


def test_lower_type_keeps_raw_function_pointer_signature_shape() -> None:
    fn_ptr = FunctionPtr(
        ret=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
        params=[
            Pointer(pointee=None),
            TypeRef(
                decl_id="typedef:my_uint",
                name="my_uint",
                canonical=IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4),
            ),
        ],
        is_variadic=False,
        calling_convention="c",
    )

    assert lower_type(fn_ptr) == FunctionType(
        params=[
            Param(
                name="",
                type=PointerType(pointee=None, mutability=PointerMutability.MUT, nullable=True),
            ),
            Param(name="", type=NamedType(name="my_uint")),
        ],
        ret=BuiltinType(name=MojoBuiltin.C_INT),
        abi="C",
        thin=True,
        raises=False,
    )


def test_lower_type_maps_representable_atomic_to_atomic_surface_type() -> None:
    atomic = AtomicType(value_type=IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4))

    assert lower_type(atomic) == ParametricType(
        base=ParametricBase.ATOMIC,
        args=[DTypeArg("DType.uint32")],
    )


def test_lower_type_maps_complex_and_vector_surface_forms_and_fallbacks() -> None:
    f32 = FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4)
    long_double = FloatType(float_kind=FloatKind.LONG_DOUBLE, size_bytes=16, align_bytes=16)

    assert lower_type(ComplexType(element=f32, size_bytes=8)) == ParametricType(
        base=ParametricBase.COMPLEX_SIMD,
        args=[DTypeArg("DType.float32"), ConstArg(1)],
    )
    assert lower_type(ComplexType(element=long_double, size_bytes=32)) == ArrayType(
        element=BuiltinType(name=MojoBuiltin.C_DOUBLE),
        count=2,
    )
    assert lower_type(VectorType(element=f32, count=4, size_bytes=16)) == ParametricType(
        base=ParametricBase.SIMD,
        args=[DTypeArg("DType.float32"), ConstArg(4)],
    )
    assert lower_type(VectorType(element=long_double, count=2, size_bytes=32)) == ArrayType(
        element=BuiltinType(name=MojoBuiltin.C_DOUBLE),
        count=2,
    )
    assert lower_type(VectorType(element=f32, count=None, size_bytes=16)) == ArrayType(
        element=BuiltinType(name=MojoBuiltin.UINT8),
        count=16,
    )


def test_lower_type_maps_unsupported_type_to_inline_bytes_when_sized() -> None:
    unsupported = UnsupportedType(
        category="unknown",
        spelling="mystery_t",
        reason="not modeled",
        size_bytes=16,
        align_bytes=8,
    )

    assert lower_type(unsupported) == ArrayType(
        element=BuiltinType(name=MojoBuiltin.UINT8),
        count=16,
    )


def test_lower_type_maps_unsized_unsupported_type_to_opaque_pointer() -> None:
    unsupported = UnsupportedType(
        category="unknown",
        spelling="mystery_t",
        reason="not modeled",
    )

    assert lower_type(unsupported) == PointerType(
        pointee=None,
        mutability=PointerMutability.MUT,
    )


def test_lower_type_maps_missing_primitive_kinds_to_valid_surface_types() -> None:
    assert lower_type(IntType(int_kind=IntKind.WCHAR, size_bytes=4, align_bytes=4)) == NamedType(
        name="Int32"
    )
    assert lower_type(IntType(int_kind=IntKind.CHAR16, size_bytes=2, align_bytes=2)) == NamedType(
        name="UInt16"
    )
    assert lower_type(IntType(int_kind=IntKind.CHAR32, size_bytes=4, align_bytes=4)) == NamedType(
        name="UInt32"
    )
    assert lower_type(
        IntType(int_kind=IntKind.EXT_INT, size_bytes=8, align_bytes=8, ext_bits=33)
    ) == NamedType(name="Int64")
    assert lower_type(
        IntType(int_kind=IntKind.INT128, size_bytes=16, align_bytes=16)
    ) == BuiltinType(name=MojoBuiltin.INT128)
    assert lower_type(
        IntType(int_kind=IntKind.UINT128, size_bytes=16, align_bytes=16)
    ) == BuiltinType(name=MojoBuiltin.UINT128)


def test_lower_type_maps_float128_to_inline_bytes() -> None:
    assert lower_type(
        FloatType(float_kind=FloatKind.FLOAT128, size_bytes=16, align_bytes=16)
    ) == ArrayType(
        element=BuiltinType(name=MojoBuiltin.UINT8),
        count=16,
    )


def test_lower_type_caches_recursively_without_looping_for_nested_typeref_shapes() -> None:
    lowerer = LowerTypePass()
    alias = TypeRef(
        decl_id="typedef:node_handle_t",
        name="node_handle_t",
        canonical=Pointer(
            pointee=TypeRef(
                decl_id="typedef:node_handle_t",
                name="node_handle_t",
                canonical=VoidType(),
            )
        ),
    )

    first = lowerer.run(alias)
    second = lowerer.run(alias)

    assert first == NamedType(name="node_handle_t")
    assert second == first
