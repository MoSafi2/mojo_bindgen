"""Public analysis API for CIR passes and CIR -> MojoIR mapping."""

from mojo_bindgen.analysis.cir.reachability import (
    SignatureRecordStubOptions,
    SignatureRecordStubPass,
    SignatureRecordStubResult,
    materialize_signature_record_stubs,
)
from mojo_bindgen.analysis.cir.reference_validation import (
    ReferenceValidationError,
    ValidateReferencesPass,
)
from mojo_bindgen.analysis.cir.validate_ir import IRValidationError, ValidateIRPass
from mojo_bindgen.analysis.facts.alias_classification import (
    AliasClass,
    AliasClassification,
    AliasInfo,
    classify_aliases,
)
from mojo_bindgen.analysis.facts.context import AnalysisContext, build_analysis_context
from mojo_bindgen.analysis.facts.dependency_graph import (
    DeclDependencyGraph,
    build_decl_dependency_graph,
)
from mojo_bindgen.analysis.facts.record_storage import (
    ByValueEmbeddingDecision,
    RecordStorageFacts,
    RecordStorageKind,
    analyze_record_storage,
    analyze_record_storage_facts,
)
from mojo_bindgen.analysis.mojo.const_expr_mapping import (
    ConstExprMappingError,
    MapConstExprPass,
    map_const_expr,
)
from mojo_bindgen.analysis.mojo.decl_mapping import UnitMappingError
from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.mojo.record_policies import (
    AssignRecordPoliciesError,
    AssignRecordPoliciesPass,
    PolicyInferencePass,
    assign_record_policies,
)
from mojo_bindgen.analysis.mojo.struct_mapping import (
    StructMappingContext,
    StructMappingError,
    map_struct,
)
from mojo_bindgen.analysis.mojo.type_mapping import (
    MapTypePass,
    TypeMappingError,
    map_type,
)
from mojo_bindgen.analysis.mojo.union_mapping import (
    MapUnionPass,
    UnionMappingError,
    map_union,
)
from mojo_bindgen.analysis.mojo.unit_mapping import (
    MapUnitPass,
    map_unit,
)
from mojo_bindgen.analysis.pipeline import (
    AnalysisArtifacts,
    AnalysisOrchestrator,
    AnalysisResult,
    run_ir_passes,
)
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes

__all__ = [
    "AssignRecordPoliciesError",
    "AssignRecordPoliciesPass",
    "AnalysisResult",
    "AnalysisArtifacts",
    "AnalysisContext",
    "AnalysisOrchestrator",
    "AliasClass",
    "AliasClassification",
    "AliasInfo",
    "ConstExprMappingError",
    "IRValidationError",
    "MapConstExprPass",
    "MapTypePass",
    "MapUnionPass",
    "MapUnitPass",
    "MojoEmitOptions",
    "PolicyInferencePass",
    "DeclDependencyGraph",
    "ReferenceValidationError",
    "ByValueEmbeddingDecision",
    "RecordStorageFacts",
    "RecordStorageKind",
    "SignatureRecordStubOptions",
    "SignatureRecordStubPass",
    "SignatureRecordStubResult",
    "StructMappingContext",
    "StructMappingError",
    "TypeMappingError",
    "ValidateIRPass",
    "ValidateReferencesPass",
    "UnionMappingError",
    "UnitMappingError",
    "TypeWalkOptions",
    "assign_record_policies",
    "analyze_record_storage",
    "analyze_record_storage_facts",
    "build_analysis_context",
    "build_decl_dependency_graph",
    "classify_aliases",
    "iter_type_nodes",
    "map_const_expr",
    "map_struct",
    "map_type",
    "map_union",
    "map_unit",
    "materialize_signature_record_stubs",
    "run_ir_passes",
]
