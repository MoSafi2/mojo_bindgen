"""Final Mojo semantic assembly pass producing :class:`AnalyzedUnit`."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import TypeMapper
from mojo_bindgen.ir import Struct, Unit
from mojo_bindgen.analysis.model import (
    AnalyzedBitfieldLayout,
    AnalyzedBitfieldMember,
    AnalyzedBitfieldStorage,
    AnalyzedCallbackAlias,
    AnalyzedConst,
    AnalyzedEnum,
    AnalyzedField,
    AnalyzedFunction,
    AnalyzedGlobalVar,
    AnalyzedMacro,
    AnalyzedOpaqueStorage,
    AnalyzedPaddingField,
    AnalyzedStruct,
    AnalyzedStructInitializer,
    AnalyzedStructInitParam,
    AnalyzedTypedef,
    AnalyzedUnion,
    AnalyzedUnit,
    GlobalVarKind,
    TailDecl,
)
from mojo_bindgen.analysis.callbacks import (
    CallbackAlias,
    CallbackAliasInfo,
    CollectCallbackAliasesPass,
)
from mojo_bindgen.analysis.imports import (
    CollectSemanticNeedsPass,
    ImportNeeds,
)
from mojo_bindgen.analysis.layout import ComputeLayoutFactsPass, build_register_passable_map, struct_by_decl_id
from mojo_bindgen.analysis.names import CollectEmissionNamesPass
from mojo_bindgen.analysis.struct_analysis import AnalyzeStructLoweringPass
from mojo_bindgen.analysis.tail_decl_analysis import AnalyzeTailDeclPass
from mojo_bindgen.analysis.union_analysis import AnalyzeUnionLoweringPass


@dataclass
class _SemanticContext:
    """Precomputed facts for one :func:`analyze_unit_semantics` run (module-internal)."""

    options: MojoEmitOptions
    layout_facts: object
    name_facts: object
    callback_info: CallbackAliasInfo
    import_needs: ImportNeeds
    semantic_fallback_notes: tuple[str, ...]
    union_facts: object
    type_mapper: TypeMapper


class AssembleEmitModelPass:
    """Assemble concrete pass outputs into the final render-ready analyzed unit."""

    def run(
        self,
        unit: Unit,
        *,
        options: MojoEmitOptions,
        import_needs: ImportNeeds,
        semantic_fallback_notes: tuple[str, ...],
        union_facts,
        callback_info: CallbackAliasInfo,
        name_facts,
        ordered_incomplete_structs: tuple[AnalyzedStruct, ...],
        ordered_structs: tuple[AnalyzedStruct, ...],
        tail_decls: tuple[TailDecl, ...],
        callback_aliases: tuple[AnalyzedCallbackAlias, ...],
        ffi_scalar_import_names: frozenset[str],
    ) -> AnalyzedUnit:
        needs_global_symbol_helpers = any(
            isinstance(d, AnalyzedGlobalVar) and d.kind == "wrapper" for d in tail_decls
        )
        return AnalyzedUnit(
            unit=unit,
            opts=options,
            needs_opaque_imports=import_needs.opaque,
            needs_simd_import=import_needs.simd,
            needs_complex_import=import_needs.complex,
            needs_atomic_import=import_needs.atomic,
            needs_global_symbol_helpers=needs_global_symbol_helpers,
            semantic_fallback_notes=semantic_fallback_notes,
            union_alias_names=union_facts.union_alias_names,
            unsafe_union_names=union_facts.unsafe_union_names,
            emitted_typedef_mojo_names=name_facts.emitted_typedef_names,
            callback_aliases=callback_aliases,
            callback_signature_names=callback_info.signature_names,
            global_callback_aliases=callback_info.global_aliases,
            ordered_incomplete_structs=ordered_incomplete_structs,
            ordered_structs=ordered_structs,
            unions=union_facts.unions,
            tail_decls=tail_decls,
            ffi_scalar_import_names=ffi_scalar_import_names,
        )


def analyze_unit_semantics(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    layout_facts = ComputeLayoutFactsPass().run(unit)
    name_facts = CollectEmissionNamesPass().run(
        unit,
        ordered_structs=layout_facts.ordered_structs,
        incomplete_structs=layout_facts.incomplete_structs,
    )
    callback_info = CollectCallbackAliasesPass().run(
        unit,
        emitted_typedef_names=name_facts.emitted_typedef_names,
    )
    union_facts = AnalyzeUnionLoweringPass().run(
        unit,
        ffi_origin=options.ffi_origin,
        ffi_scalar_style=options.ffi_scalar_style,
    )
    import_needs, semantic_fallback_notes = CollectSemanticNeedsPass().run(unit)
    type_mapper = TypeMapper(
        ffi_origin=options.ffi_origin,
        union_alias_names=union_facts.union_alias_names,
        unsafe_union_names=union_facts.unsafe_union_names,
        typedef_mojo_names=name_facts.emitted_typedef_names,
        callback_signature_names=callback_info.signature_names,
        ffi_scalar_style=options.ffi_scalar_style,
    )

    struct_pass = AnalyzeStructLoweringPass()
    ordered_incomplete_structs = tuple(
        struct_pass.run(
            decl,
            struct_map=layout_facts.struct_map,
            register_passable=layout_facts.register_passable_by_decl_id.get(decl.decl_id, False),
            field_callback_aliases=callback_info.field_aliases,
            options=options,
            type_mapper=type_mapper,
        )
        for decl in layout_facts.incomplete_structs
    )
    ordered_structs = tuple(
        struct_pass.run(
            decl,
            struct_map=layout_facts.struct_map,
            register_passable=layout_facts.register_passable_by_decl_id.get(decl.decl_id, False),
            field_callback_aliases=callback_info.field_aliases,
            options=options,
            type_mapper=type_mapper,
        )
        for decl in layout_facts.ordered_structs
    )
    tail_decls, analyzed_callback_aliases = AnalyzeTailDeclPass().run(
        unit,
        name_facts=name_facts,
        callback_info=callback_info,
        layout_facts=layout_facts,
        type_mapper=type_mapper,
    )
    type_mapper.warm_ffi_scalar_imports_from_unit(unit)
    return AssembleEmitModelPass().run(
        unit,
        options=options,
        import_needs=import_needs,
        semantic_fallback_notes=semantic_fallback_notes,
        union_facts=union_facts,
        callback_info=callback_info,
        name_facts=name_facts,
        ordered_incomplete_structs=ordered_incomplete_structs,
        ordered_structs=ordered_structs,
        tail_decls=tail_decls,
        callback_aliases=analyzed_callback_aliases,
        ffi_scalar_import_names=type_mapper.ffi_scalar_import_names,
    )


def analyzed_struct_for_test(
    decl: Struct,
    *,
    struct_by_name: dict[str, Struct],
    options: MojoEmitOptions | None = None,
) -> AnalyzedStruct:
    reg = build_register_passable_map(struct_by_name).get(decl.decl_id, False)
    mapper = TypeMapper(
        ffi_origin=(options or MojoEmitOptions()).ffi_origin,
        union_alias_names=frozenset(),
        unsafe_union_names=frozenset(),
        typedef_mojo_names=frozenset(),
        callback_signature_names=frozenset(),
        ffi_scalar_style=(options or MojoEmitOptions()).ffi_scalar_style,
    )
    return AnalyzeStructLoweringPass().run(
        decl,
        struct_map=struct_by_name,
        register_passable=reg,
        field_callback_aliases=None,
        options=options or MojoEmitOptions(),
        type_mapper=mapper,
    )


def analyze_unit(unit: Unit, options: MojoEmitOptions) -> AnalyzedUnit:
    """Run the IR pass pipeline and final semantic analysis over ``unit``."""
    from mojo_bindgen.analysis.pipeline import run_ir_passes

    return analyze_unit_semantics(run_ir_passes(unit), options)


class AnalyzeForMojoPass:
    """Produce final Mojo-specific analyzed output from normalized IR."""

    def __init__(self, options: MojoEmitOptions) -> None:
        self._options = options

    def run(self, unit: Unit) -> AnalyzedUnit:
        return analyze_unit_semantics(unit, self._options)


__all__ = [
    "AnalyzeForMojoPass",
    "AnalyzedBitfieldLayout",
    "AnalyzedBitfieldMember",
    "AnalyzedBitfieldStorage",
    "AnalyzedCallbackAlias",
    "AnalyzedConst",
    "AnalyzedEnum",
    "AnalyzedField",
    "AnalyzedFunction",
    "AnalyzedGlobalVar",
    "AnalyzedMacro",
    "AnalyzedOpaqueStorage",
    "AnalyzedPaddingField",
    "AnalyzedStruct",
    "AnalyzedStructInitializer",
    "AnalyzedStructInitParam",
    "AnalyzedTypedef",
    "AnalyzedUnion",
    "AnalyzedUnit",
    "AssembleEmitModelPass",
    "CallbackAlias",
    "GlobalVarKind",
    "TailDecl",
    "analyze_unit",
    "analyze_unit_semantics",
    "analyzed_struct_for_test",
    "struct_by_decl_id",
]
