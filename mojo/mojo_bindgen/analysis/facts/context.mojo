from std.memory import ArcPointer
from ...ir import *
from .indexes import DeclIndexes, build_decl_indexes
from .target import TargetQueries
from .dependency_graph import DeclDependencyGraph, build_decl_dependency_graph
from .alias_classification import AliasClassification, classify_aliases
from .record_layout import RecordLayoutFacts, analyze_record_layout
from .record_storage import RecordStorageFacts, analyze_record_storage_facts
from ..cir.validate_ir import ValidateIRPass
from ..mojo.type_mapping import MapTypePass


@fieldwise_init
struct AnalysisContext(Copyable, Movable):
    var unit: ArcPointer[Unit]
    var target_queries: TargetQueries
    var indexes: DeclIndexes
    var dependency_graph: DeclDependencyGraph
    var alias_classification: AliasClassification
    var record_layouts: Dict[String, RecordLayoutFacts]
    var record_storage: Dict[String, RecordStorageFacts]


def build_analysis_context(unit: ArcPointer[Unit]) raises -> AnalysisContext:
    _ = ValidateIRPass().run(unit.ptr()[])
    var indexes = build_decl_indexes(unit.ptr()[])
    var queries = TargetQueries(unit.ptr()[].target_abi.copy())
    var layouts = Dict[String, RecordLayoutFacts]()
    for record in indexes.records_by_decl_id.values():
        layouts[record.decl_id] = analyze_record_layout(record)
    var graph = build_decl_dependency_graph(unit.ptr()[])
    var aliases = classify_aliases(unit.ptr()[])
    var storage = analyze_record_storage_facts(
        indexes.records_by_decl_id, layouts, MapTypePass(queries.copy())
    )
    return AnalysisContext(unit.copy(), queries^, indexes^, graph^, aliases^, layouts^, storage^)
