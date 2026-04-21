"""Backend-neutral import/fallback fact collection over normalized IR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, any_type_node, iter_type_nodes
from mojo_bindgen.codegen.mojo_mapper import map_atomic_type, map_complex_simd, map_vector_simd
from mojo_bindgen.ir import (
    AtomicType,
    ComplexType,
    Function,
    FunctionPtr,
    GlobalVar,
    OpaqueRecordRef,
    Pointer,
    Struct,
    Type,
    Typedef,
    Unit,
    UnsupportedType,
    VectorType,
)

_OPAQUE_IMPORT_WALK = TypeWalkOptions(
    descend_function_ptr=False,
    descend_vector_element=False,
)
_IMPORT_WALK = TypeWalkOptions(
    descend_function_ptr=True,
    descend_vector_element=False,
)
_FALLBACK_WALK = TypeWalkOptions(
    descend_function_ptr=True,
    descend_vector_element=True,
)


@dataclass(frozen=True)
class ImportNeeds:
    opaque: bool
    simd: bool
    complex: bool
    atomic: bool


def _type_needs_opaque_pointer_import(t: Type) -> bool:
    return any_type_node(
        t,
        lambda u: (
            isinstance(u, FunctionPtr)
            or (isinstance(u, Pointer) and u.pointee is None)
            or isinstance(u, (OpaqueRecordRef, UnsupportedType))
        ),
        options=_OPAQUE_IMPORT_WALK,
    )


def _type_needs_simd_import(t: Type) -> bool:
    return any_type_node(
        t,
        lambda u: isinstance(u, VectorType) and map_vector_simd(u) is not None,
        options=_IMPORT_WALK,
    )


def _type_needs_complex_import(t: Type) -> bool:
    return any_type_node(
        t,
        lambda u: isinstance(u, ComplexType) and map_complex_simd(u) is not None,
        options=_IMPORT_WALK,
    )


def _type_needs_atomic_import(t: Type) -> bool:
    return any_type_node(
        t,
        lambda u: isinstance(u, AtomicType) and map_atomic_type(u) is not None,
        options=_IMPORT_WALK,
    )


def _collect_fallback_notes_for_type(t: Type, notes: set[str]) -> None:
    for u in iter_type_nodes(t, options=_FALLBACK_WALK):
        if isinstance(u, AtomicType) and map_atomic_type(u) is None:
            notes.add(
                "some atomic types were mapped to their underlying non-atomic Mojo type because Atomic[dtype] was not representable"
            )
        elif isinstance(u, ComplexType) and map_complex_simd(u) is None:
            notes.add(
                "some complex C types were mapped as InlineArray[scalar, 2] because ComplexSIMD[dtype, 1] was not representable"
            )
        elif isinstance(u, VectorType) and map_vector_simd(u) is None:
            notes.add(
                "some vector C types were mapped as InlineArray[...] because SIMD[dtype, size] was not representable"
            )


def _iter_decl_types(unit: Unit):
    for decl in unit.decls:
        if isinstance(decl, Struct) and not decl.is_union:
            for field in decl.fields:
                yield field.type
        elif isinstance(decl, Function):
            yield decl.ret
            for param in decl.params:
                yield param.type
        elif isinstance(decl, Typedef):
            yield decl.canonical
        elif isinstance(decl, GlobalVar):
            yield decl.type


def collect_unit_import_and_fallback_needs(
    unit: Unit,
) -> tuple[ImportNeeds, tuple[str, ...]]:
    """Single scan of ``unit.decls`` for import flags and semantic fallback notes."""
    notes: set[str] = set()
    opaque = simd = complex = atomic = False
    for t in _iter_decl_types(unit):
        opaque = opaque or _type_needs_opaque_pointer_import(t)
        simd = simd or _type_needs_simd_import(t)
        complex = complex or _type_needs_complex_import(t)
        atomic = atomic or _type_needs_atomic_import(t)
        _collect_fallback_notes_for_type(t, notes)
    return (
        ImportNeeds(opaque=opaque, simd=simd, complex=complex, atomic=atomic),
        tuple(sorted(notes)),
    )


class CollectSemanticNeedsPass:
    """Collect backend-neutral import/fallback semantic facts."""

    def run(self, unit: Unit) -> tuple[ImportNeeds, tuple[str, ...]]:
        return collect_unit_import_and_fallback_needs(unit)
