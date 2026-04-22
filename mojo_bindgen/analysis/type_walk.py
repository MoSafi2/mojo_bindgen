"""Shared traversal helpers for recursive IR :class:`Type` trees."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass

from mojo_bindgen.ir import (
    Array,
    AtomicType,
    FunctionPtr,
    Pointer,
    QualifiedType,
    Type,
    TypeRef,
    VectorType,
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


def iter_type_nodes(t: Type, *, options: TypeWalkOptions | None = None) -> Iterator[Type]:
    """Yield ``t`` and selected descendants in preorder."""
    cfg = options or TypeWalkOptions()

    def walk(node: Type) -> Iterator[Type]:
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
        if isinstance(node, Pointer):
            if cfg.descend_pointer and node.pointee is not None:
                yield from walk(node.pointee)
            return
        if isinstance(node, Array):
            if cfg.descend_array:
                yield from walk(node.element)
            return
        if isinstance(node, FunctionPtr):
            if cfg.descend_function_ptr:
                yield from walk(node.ret)
                for param in node.params:
                    yield from walk(param)
            return
        if isinstance(node, VectorType):
            if cfg.descend_vector_element:
                yield from walk(node.element)

    yield from walk(t)


def any_type_node(
    t: Type,
    predicate: Callable[[Type], bool],
    *,
    options: TypeWalkOptions | None = None,
) -> bool:
    """Return whether any traversed node satisfies ``predicate``."""
    return any(predicate(node) for node in iter_type_nodes(t, options=options))


def collect_type_nodes(
    t: Type,
    predicate: Callable[[Type], bool],
    *,
    options: TypeWalkOptions | None = None,
) -> tuple[Type, ...]:
    """Collect traversed nodes that satisfy ``predicate``."""
    return tuple(node for node in iter_type_nodes(t, options=options) if predicate(node))


def _walk_typeref_nodes(t: Type, out: list[TypeRef]) -> None:
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
