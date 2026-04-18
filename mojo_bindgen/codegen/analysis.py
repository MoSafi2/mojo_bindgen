"""Compatibility surface for analyzed codegen data.

The actual semantic-analysis behavior now lives under :mod:`mojo_bindgen.passes`.
This module keeps the analyzed data shapes and a small compatibility API for
older imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import Const, Enum, Field, Function, FunctionPtr, GlobalVar, MacroDecl, Struct, Typedef, Unit


@dataclass(frozen=True)
class AnalyzedField:
    """Derived field metadata needed by the renderer."""

    field: Field
    index: int
    mojo_name: str
    callback_alias_name: str | None = None


@dataclass(frozen=True)
class AnalyzedStruct:
    """Derived struct-level emission decisions."""

    decl: Struct
    register_passable: bool
    align_decorator: int | None
    align_stride_warning: bool
    align_omit_comment: str | None
    fields: tuple[AnalyzedField, ...]


@dataclass(frozen=True)
class AnalyzedTypedef:
    """Derived typedef policy."""

    decl: Typedef
    skip_duplicate: bool
    callback_alias_name: str | None = None


FunctionKind = Literal["wrapper", "variadic_stub", "non_register_return_stub"]


@dataclass(frozen=True)
class AnalyzedFunction:
    """Derived function emission decisions."""

    decl: Function
    kind: FunctionKind
    param_names: tuple[str, ...]
    ret_callback_alias_name: str | None = None
    param_callback_alias_names: tuple[str | None, ...] = ()


@dataclass(frozen=True)
class CallbackAlias:
    """Generated callback signature alias for a surfaced function-pointer type."""

    name: str
    fp: FunctionPtr


@dataclass(frozen=True)
class AnalyzedUnion:
    """Derived union lowering decisions."""

    decl: Struct
    uses_unsafe_union: bool


TailDecl = Enum | Const | MacroDecl | GlobalVar | AnalyzedTypedef | AnalyzedFunction


@dataclass(frozen=True)
class AnalyzedUnit:
    """Unit-level semantic analysis for Mojo generation."""

    unit: Unit
    opts: MojoEmitOptions
    needs_opaque_imports: bool
    needs_simd_import: bool
    needs_complex_import: bool
    needs_atomic_import: bool
    semantic_fallback_notes: tuple[str, ...]
    unsafe_union_names: frozenset[str]
    emitted_typedef_mojo_names: frozenset[str]
    callback_aliases: tuple[CallbackAlias, ...]
    callback_signature_names: frozenset[str]
    global_callback_aliases: dict[str, str]
    ordered_structs: tuple[AnalyzedStruct, ...]
    unions: tuple[AnalyzedUnion, ...]
    tail_decls: tuple[TailDecl, ...]


def analyze_unit(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    """Run the IR pass pipeline and final semantic analysis over ``unit``."""
    from mojo_bindgen.passes.pipeline import run_ir_passes
    from mojo_bindgen.passes.analyze_for_mojo import analyze_unit_semantics as _impl

    return _impl(run_ir_passes(unit), options)


def analyze_unit_semantics(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    """Compatibility wrapper for final semantic analysis on normalized IR."""
    from mojo_bindgen.passes.analyze_for_mojo import analyze_unit_semantics as _impl

    return _impl(unit, options)


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Compatibility wrapper for decl-id lookups implemented in the final pass."""
    from mojo_bindgen.passes.analyze_for_mojo import struct_by_decl_id as _impl

    return _impl(unit)


def analyzed_struct_for_test(
    decl: Struct,
    *,
    options: MojoEmitOptions,
    struct_by_name: dict[str, Struct],
) -> AnalyzedStruct:
    """Compatibility wrapper for struct-level semantic analysis in tests."""
    from mojo_bindgen.passes.analyze_for_mojo import analyzed_struct_for_test as _impl

    return _impl(decl, options=options, struct_by_name=struct_by_name)


__all__ = [
    "AnalyzedField",
    "AnalyzedStruct",
    "AnalyzedTypedef",
    "AnalyzedFunction",
    "AnalyzedUnion",
    "AnalyzedUnit",
    "CallbackAlias",
    "FunctionKind",
    "TailDecl",
    "analyze_unit",
    "analyze_unit_semantics",
    "analyzed_struct_for_test",
    "struct_by_decl_id",
]
