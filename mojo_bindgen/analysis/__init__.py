"""Public analysis API for CIR passes and CIR -> MojoIR lowering."""

from mojo_bindgen.analysis.alias_classification import (
    AliasClass,
    AliasClassification,
    AliasInfo,
    classify_aliases,
)
from mojo_bindgen.analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
    lower_const_expr,
)
from mojo_bindgen.analysis.context import AnalysisContext, build_analysis_context
from mojo_bindgen.analysis.decl_lowerer import UnitLoweringError
from mojo_bindgen.analysis.dependency_graph import (
    DeclDependencyGraph,
    build_decl_dependency_graph,
)
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.orchestrator import (
    AnalysisArtifacts,
    AnalysisOrchestrator,
    AnalysisResult,
    run_ir_passes,
)
from mojo_bindgen.analysis.reachability import (
    SignatureRecordStubOptions,
    SignatureRecordStubPass,
    SignatureRecordStubResult,
    materialize_signature_record_stubs,
)
from mojo_bindgen.analysis.record_policies import (
    AssignRecordPoliciesError,
    AssignRecordPoliciesPass,
    PolicyInferencePass,
    assign_record_policies,
)
from mojo_bindgen.analysis.record_shape import (
    ByValueRecordShape,
    RecordAnalysisFacts,
    RecordShapeFacts,
    RecordStorageKind,
    analyze_record_shape,
    analyze_record_shapes,
)
from mojo_bindgen.analysis.reference_validation import (
    ReferenceValidationError,
    ValidateReferencesPass,
)
from mojo_bindgen.analysis.struct_lowering import (
    StructLoweringContext,
    StructLoweringError,
    lower_struct,
)
from mojo_bindgen.analysis.type_lowering import (
    LowerTypePass,
    TypeLoweringError,
    lower_type,
)
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.analysis.union_lowering import (
    LowerUnionPass,
    UnionLoweringError,
    lower_union,
)
from mojo_bindgen.analysis.unit_lowering import (
    LowerUnitPass,
    lower_unit,
)
from mojo_bindgen.analysis.validate_ir import IRValidationError, ValidateIRPass

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
    "ConstExprLoweringError",
    "IRValidationError",
    "LowerConstExprPass",
    "LowerTypePass",
    "LowerUnionPass",
    "LowerUnitPass",
    "MojoEmitOptions",
    "PolicyInferencePass",
    "DeclDependencyGraph",
    "ReferenceValidationError",
    "ByValueRecordShape",
    "RecordAnalysisFacts",
    "RecordShapeFacts",
    "RecordStorageKind",
    "SignatureRecordStubOptions",
    "SignatureRecordStubPass",
    "SignatureRecordStubResult",
    "StructLoweringContext",
    "StructLoweringError",
    "TypeLoweringError",
    "ValidateIRPass",
    "ValidateReferencesPass",
    "UnionLoweringError",
    "UnitLoweringError",
    "TypeWalkOptions",
    "assign_record_policies",
    "analyze_record_shape",
    "analyze_record_shapes",
    "build_analysis_context",
    "build_decl_dependency_graph",
    "classify_aliases",
    "iter_type_nodes",
    "lower_const_expr",
    "lower_struct",
    "lower_type",
    "lower_union",
    "lower_unit",
    "materialize_signature_record_stubs",
    "run_ir_passes",
]
