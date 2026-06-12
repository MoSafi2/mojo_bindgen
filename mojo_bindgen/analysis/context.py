"""Shared analysis facts for the CIR -> MojoIR pipeline."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.alias_classification import AliasClassification, classify_aliases
from mojo_bindgen.analysis.dependency_graph import DeclDependencyGraph, build_decl_dependency_graph
from mojo_bindgen.analysis.lowering_support import record_by_decl_id
from mojo_bindgen.analysis.record_layout import RecordLayoutFacts, analyze_record_layout
from mojo_bindgen.analysis.record_shape import RecordAnalysisFacts, analyze_record_shapes
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

    records = record_by_decl_id(unit)
    record_layouts = {
        decl_id: analyze_record_layout(
            record,
            target_abi=unit.target_abi,
            record_map=records,
        )
        for decl_id, record in records.items()
    }
    dependency_graph = build_decl_dependency_graph(unit)
    alias_classification = classify_aliases(unit)
    record_shapes = analyze_record_shapes(records, record_layouts)
    return AnalysisContext(
        unit=unit,
        records_by_decl_id=records,
        typedefs_by_decl_id={
            decl.decl_id: decl for decl in unit.decls if isinstance(decl, Typedef)
        },
        enums_by_decl_id={decl.decl_id: decl for decl in unit.decls if isinstance(decl, Enum)},
        functions_by_decl_id={
            decl.decl_id: decl for decl in unit.decls if isinstance(decl, Function)
        },
        globals_by_decl_id={
            decl.decl_id: decl for decl in unit.decls if isinstance(decl, GlobalVar)
        },
        consts_by_name={decl.name: decl for decl in unit.decls if isinstance(decl, Const)},
        macros_by_name={decl.name: decl for decl in unit.decls if isinstance(decl, MacroDecl)},
        dependency_graph=dependency_graph,
        alias_classification=alias_classification,
        record_layouts=record_layouts,
        record_shapes=record_shapes,
    )


__all__ = [
    "AnalysisContext",
    "build_analysis_context",
]
