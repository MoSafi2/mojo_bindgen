"""Public analysis API for normalized IR processing and Mojo lowering."""

from mojo_bindgen.analysis.analyze_for_mojo import (
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
    AnalyzeForMojoPass,
    AssembleEmitModelPass,
    CallbackAlias,
    GlobalVarKind,
    TailDecl,
    analyze_unit,
    analyze_unit_semantics,
    analyzed_struct_for_test,
    struct_by_decl_id,
)
from mojo_bindgen.analysis.callbacks import (
    CollectCallbackAliasesPass,
)
from mojo_bindgen.analysis.imports import CollectSemanticNeedsPass
from mojo_bindgen.analysis.layout import ComputeLayoutFactsPass
from mojo_bindgen.analysis.names import CollectEmissionNamesPass
from mojo_bindgen.analysis.pipeline import run_ir_passes
from mojo_bindgen.analysis.reachability import (
    ReachabilityMaterializePass,
    ReachabilityMaterializeResult,
    ReachabilityOptions,
    materialize_reachable_struct_refs,
)
from mojo_bindgen.analysis.struct_analysis import AnalyzeStructLoweringPass
from mojo_bindgen.analysis.tail_decl_analysis import AnalyzeTailDeclPass
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.analysis.union_analysis import AnalyzeUnionLoweringPass, UnionFacts
from mojo_bindgen.analysis.validate_ir import IRValidationError, ValidateIRPass

__all__ = [
    "AnalyzeForMojoPass",
    "AnalyzeStructLoweringPass",
    "AnalyzeTailDeclPass",
    "AnalyzeUnionLoweringPass",
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
    "CollectCallbackAliasesPass",
    "CollectEmissionNamesPass",
    "CollectSemanticNeedsPass",
    "ComputeLayoutFactsPass",
    "GlobalVarKind",
    "IRValidationError",
    "ReachabilityMaterializePass",
    "ReachabilityMaterializeResult",
    "ReachabilityOptions",
    "TailDecl",
    "TypeWalkOptions",
    "UnionFacts",
    "ValidateIRPass",
    "analyze_unit",
    "analyze_unit_semantics",
    "analyzed_struct_for_test",
    "iter_type_nodes",
    "materialize_reachable_struct_refs",
    "run_ir_passes",
    "struct_by_decl_id",
]
