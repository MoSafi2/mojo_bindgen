from __future__ import annotations

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.ir import (
    Array,
    AtomicType,
    FloatKind,
    FloatType,
    FunctionPtr,
    IntKind,
    IntType,
    Pointer,
    QualifiedType,
    TypeRef,
    VectorType,
    VoidType,
)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def test_iter_type_nodes_peels_common_wrappers_by_default() -> None:
    inner = _i32()
    wrapped = TypeRef(
        decl_id="typedef:wrapped",
        name="wrapped",
        canonical=QualifiedType(
            unqualified=AtomicType(
                value_type=Pointer(
                    pointee=Array(element=inner, size=4),
                )
            )
        ),
    )

    nodes = tuple(type(node).__name__ for node in iter_type_nodes(wrapped))
    assert nodes == (
        "TypeRef",
        "QualifiedType",
        "AtomicType",
        "Pointer",
        "Array",
        "IntType",
    )


def test_iter_type_nodes_can_skip_function_pointer_descent() -> None:
    fp = FunctionPtr(ret=VoidType(), params=[_i32()], is_variadic=False)

    shallow = tuple(
        type(node).__name__
        for node in iter_type_nodes(fp, options=TypeWalkOptions(descend_function_ptr=False))
    )
    deep = tuple(type(node).__name__ for node in iter_type_nodes(fp))

    assert shallow == ("FunctionPtr",)
    assert deep == ("FunctionPtr", "VoidType", "IntType")


def test_iter_type_nodes_can_descend_vector_elements_when_requested() -> None:
    vector = VectorType(
        element=FloatType(float_kind=FloatKind.FLOAT, size_bytes=4, align_bytes=4),
        count=4,
        size_bytes=16,
    )

    shallow = tuple(type(node).__name__ for node in iter_type_nodes(vector))
    deep = tuple(
        type(node).__name__
        for node in iter_type_nodes(vector, options=TypeWalkOptions(descend_vector_element=True))
    )

    assert shallow == ("VectorType",)
    assert deep == ("VectorType", "FloatType")
