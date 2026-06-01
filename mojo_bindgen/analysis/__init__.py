"""Public analysis API for CIR passes and CIR -> MojoIR lowering."""

from mojo_bindgen.analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
    lower_const_expr,
)
from mojo_bindgen.analysis.decl_lowerer import UnitLoweringError
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.orchestrator import (
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
    "AnalysisOrchestrator",
    "ConstExprLoweringError",
    "IRValidationError",
    "LowerConstExprPass",
    "LowerTypePass",
    "LowerUnionPass",
    "LowerUnitPass",
    "MojoEmitOptions",
    "PolicyInferencePass",
    "SignatureRecordStubOptions",
    "SignatureRecordStubPass",
    "SignatureRecordStubResult",
    "StructLoweringContext",
    "StructLoweringError",
    "TypeLoweringError",
    "ValidateIRPass",
    "UnionLoweringError",
    "UnitLoweringError",
    "TypeWalkOptions",
    "assign_record_policies",
    "iter_type_nodes",
    "lower_const_expr",
    "lower_struct",
    "lower_type",
    "lower_union",
    "lower_unit",
    "materialize_signature_record_stubs",
    "run_ir_passes",
]
