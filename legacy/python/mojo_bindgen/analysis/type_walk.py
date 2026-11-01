"""Shared traversal helpers for recursive IR :class:`CType` trees."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import assert_never

from mojo_bindgen.ir import (
    AtomicType,
    CArray,
    CFunctionPtr,
    ComplexType,
    CPointer,
    CType,
    EnumRef,
    FloatType,
    IntType,
    OpaqueRecordRef,
    QualifiedType,
    StructRef,
    TypeRef,
    UnsupportedType,
    VectorType,
    VoidType,
)


@dataclass(frozen=True)
class TypeWalkOptions:
    """Control which wrapper/container nodes should be traversed."""

    peel_typeref: bool = True
    peel_qualified: bool = True
    peel_atomic: bool = True
    descend_pointer: bool = True
    descend_array: bool = True
    descend_function_ptr: bool = True
    descend_vector_element: bool = False


def structural_children(node: CType) -> tuple[CType, ...]:
    """All owning edges, independently of traversal filtering policy."""
    match node:
        case QualifiedType():
            return (node.unqualified,)
        case AtomicType():
            return (node.value_type,)
        case TypeRef():
            return (node.canonical,)
        case CPointer():
            return () if node.pointee is None else (node.pointee,)
        case CArray() | VectorType() | ComplexType():
            return (node.element,)
        case CFunctionPtr():
            return (node.ret, *(param.type for param in node.params))
        case EnumRef():
            return (node.underlying,)
        case (
            VoidType()
            | IntType()
            | FloatType()
            | StructRef()
            | OpaqueRecordRef()
            | UnsupportedType()
        ):
            return ()
    assert_never(node)


def validate_type_tree(root: CType) -> None:
    """Reject structural cycles while allowing shared children and named recursion."""
    stack = [(root, False)]
    active: list[CType] = []
    while stack:
        node, leaving = stack.pop()
        if leaving:
            active.pop()
            continue
        if any(node is parent for parent in active):
            raise ValueError("structural CIR type cycle")
        active.append(node)
        stack.append((node, True))
        stack.extend((child, False) for child in reversed(structural_children(node)))


def iter_type_nodes(t: CType, *, options: TypeWalkOptions | None = None) -> Iterator[CType]:
    """Yield ``t`` and selected descendants in preorder."""
    cfg = options or TypeWalkOptions()

    def walk(node: CType) -> Iterator[CType]:
        yield node
        if isinstance(node, TypeRef):
            if cfg.peel_typeref:
                yield from walk(node.canonical)
            return
        if isinstance(node, QualifiedType):
            if cfg.peel_qualified:
                yield from walk(node.unqualified)
            return
        if isinstance(node, AtomicType):
            if cfg.peel_atomic:
                yield from walk(node.value_type)
            return
        if isinstance(node, CPointer):
            if cfg.descend_pointer and node.pointee is not None:
                yield from walk(node.pointee)
            return
        if isinstance(node, CArray):
            if cfg.descend_array:
                yield from walk(node.element)
            return
        if isinstance(node, CFunctionPtr):
            if cfg.descend_function_ptr:
                yield from walk(node.ret)
                for param in node.params:
                    yield from walk(param.type)
            return
        if isinstance(node, VectorType):
            if cfg.descend_vector_element:
                yield from walk(node.element)
            return
        if isinstance(
            node,
            (
                VoidType,
                IntType,
                FloatType,
                ComplexType,
                EnumRef,
                StructRef,
                OpaqueRecordRef,
                UnsupportedType,
            ),
        ):
            return
        assert_never(node)

    yield from walk(t)


def any_type_node(
    t: CType,
    predicate: Callable[[CType], bool],
    *,
    options: TypeWalkOptions | None = None,
) -> bool:
    """Return whether any traversed node satisfies ``predicate``."""
    return any(predicate(node) for node in iter_type_nodes(t, options=options))


def collect_type_nodes(
    t: CType,
    predicate: Callable[[CType], bool],
    *,
    options: TypeWalkOptions | None = None,
) -> tuple[CType, ...]:
    """Collect traversed nodes that satisfy ``predicate``."""
    return tuple(node for node in iter_type_nodes(t, options=options) if predicate(node))


def _walk_typeref_nodes(t: CType, out: list[TypeRef]) -> None:
    out.extend(
        node
        for node in collect_type_nodes(
            t,
            lambda node: isinstance(node, TypeRef),
            options=TypeWalkOptions(descend_vector_element=True),
        )
        if isinstance(node, TypeRef)
    )


__all__ = [
    "TypeWalkOptions",
    "any_type_node",
    "collect_type_nodes",
    "iter_type_nodes",
]
