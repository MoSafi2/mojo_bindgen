"""Explicit IR pass pipeline for post-parse transformations."""

from mojo_bindgen.passes.analyze_for_mojo import AnalyzeForMojoPass
from mojo_bindgen.passes.normalize_type_refs import NormalizeTypeRefsPass
from mojo_bindgen.passes.pipeline import run_ir_passes
from mojo_bindgen.passes.resolve_decl_refs import ResolveDeclRefsPass
from mojo_bindgen.passes.validate_ir import IRValidationError, ValidateIRPass

__all__ = [
    "AnalyzeForMojoPass",
    "IRValidationError",
    "NormalizeTypeRefsPass",
    "ResolveDeclRefsPass",
    "ValidateIRPass",
    "run_ir_passes",
]
