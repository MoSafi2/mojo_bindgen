"""Public analysis API for normalized IR processing shared by parsing and lowering."""

from mojo_bindgen.analysis.pipeline import run_ir_passes
from mojo_bindgen.analysis.reachability import (
    ReachabilityMaterializePass,
    ReachabilityMaterializeResult,
    ReachabilityOptions,
    materialize_reachable_struct_refs,
)
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, iter_type_nodes
from mojo_bindgen.analysis.validate_ir import IRValidationError, ValidateIRPass

__all__ = [
    "IRValidationError",
    "ReachabilityMaterializePass",
    "ReachabilityMaterializeResult",
    "ReachabilityOptions",
    "TypeWalkOptions",
    "ValidateIRPass",
    "iter_type_nodes",
    "materialize_reachable_struct_refs",
    "run_ir_passes",
]
