"""Explicit IR pass pipeline for post-parse transformations."""

from mojo_bindgen.passes.analyze_for_mojo import (
    AnalyzedField,
    AnalyzedFunction,
    AnalyzedGlobalVar,
    AnalyzedStruct,
    AnalyzedTypedef,
    AnalyzedUnion,
    AnalyzedUnit,
    AnalyzeForMojoPass,
    CallbackAlias,
    GlobalVarKind,
    TailDecl,
    analyze_unit,
    analyze_unit_semantics,
    analyzed_struct_for_test,
    struct_by_decl_id,
)
from mojo_bindgen.passes.pipeline import run_ir_passes
from mojo_bindgen.passes.reachability import (
    ReachabilityMaterializePass,
    ReachabilityMaterializeResult,
    ReachabilityOptions,
    materialize_reachable_struct_refs,
)
from mojo_bindgen.passes.validate_ir import IRValidationError, ValidateIRPass

__all__ = [
    "AnalyzeForMojoPass",
    "AnalyzedField",
    "AnalyzedFunction",
    "AnalyzedGlobalVar",
    "AnalyzedStruct",
    "AnalyzedTypedef",
    "AnalyzedUnion",
    "AnalyzedUnit",
    "CallbackAlias",
    "GlobalVarKind",
    "IRValidationError",
    "TailDecl",
    "analyze_unit",
    "analyze_unit_semantics",
    "analyzed_struct_for_test",
    "struct_by_decl_id",
    "ReachabilityMaterializePass",
    "ReachabilityMaterializeResult",
    "ReachabilityOptions",
    "ValidateIRPass",
    "materialize_reachable_struct_refs",
    "run_ir_passes",
]
