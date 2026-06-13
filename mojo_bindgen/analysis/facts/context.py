"""Shared analysis facts for the CIR -> MojoIR pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.facts.alias_classification import AliasClassification, classify_aliases
from mojo_bindgen.analysis.facts.dependency_graph import (
    DeclDependencyGraph,
    build_decl_dependency_graph,
)
from mojo_bindgen.analysis.facts.indexes import DeclIndexes, build_decl_indexes
from mojo_bindgen.analysis.facts.record_layout import RecordLayoutFacts, analyze_record_layout
from mojo_bindgen.analysis.facts.record_shape import RecordAnalysisFacts, analyze_record_shapes
from mojo_bindgen.ir import Const, Enum, Function, GlobalVar, MacroDecl, Struct, Typedef, Unit


@dataclass(frozen=True)
class AnalysisContext:
    """Reusable facts computed after CIR normalization and before MojoIR lowering."""

    unit: Unit
    records_by_decl_id: dict[str, Struct]
    typedefs_by_decl_id: dict[str, Typedef]
    enums_by_decl_id: dict[str, Enum]
    functions_by_decl_id: dict[str, Function]
    globals_by_decl_id: dict[str, GlobalVar]
    consts_by_name: dict[str, Const]
    macros_by_name: dict[str, MacroDecl]
    dependency_graph: DeclDependencyGraph
    alias_classification: AliasClassification
    record_layouts: dict[str, RecordLayoutFacts]
    record_shapes: dict[str, RecordAnalysisFacts]


def build_analysis_context(unit: Unit) -> AnalysisContext:
    """Build shared declaration indexes and record layout facts for ``unit``."""

    indexes = build_decl_indexes(unit)
    record_layouts = _build_record_layouts(unit, indexes)
    dependency_graph = build_decl_dependency_graph(unit)
    alias_classification = classify_aliases(unit)
    record_shapes = analyze_record_shapes(indexes.records_by_decl_id, record_layouts)
    return AnalysisContext(
        unit=unit,
        records_by_decl_id=indexes.records_by_decl_id,
        typedefs_by_decl_id=indexes.typedefs_by_decl_id,
        enums_by_decl_id=indexes.enums_by_decl_id,
        functions_by_decl_id=indexes.functions_by_decl_id,
        globals_by_decl_id=indexes.globals_by_decl_id,
        consts_by_name=indexes.consts_by_name,
        macros_by_name=indexes.macros_by_name,
        dependency_graph=dependency_graph,
        alias_classification=alias_classification,
        record_layouts=record_layouts,
        record_shapes=record_shapes,
    )


def _build_record_layouts(
    unit: Unit,
    indexes: DeclIndexes,
) -> dict[str, RecordLayoutFacts]:
    return {
        decl_id: analyze_record_layout(
            record,
            target_abi=unit.target_abi,
            record_map=indexes.records_by_decl_id,
        )
        for decl_id, record in indexes.records_by_decl_id.items()
    }


__all__ = [
    "AnalysisContext",
    "build_analysis_context",
]
