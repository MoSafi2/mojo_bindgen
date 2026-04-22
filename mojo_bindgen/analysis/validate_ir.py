"""Compatibility re-export for IR validation."""

from mojo_bindgen.new_analysis.validate_ir import IRValidationError, ValidateIRPass

__all__ = [
    "IRValidationError",
    "ValidateIRPass",
]
