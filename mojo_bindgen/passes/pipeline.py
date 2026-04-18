"""Orchestrate the Unit-to-Unit IR pass pipeline."""

from __future__ import annotations

from mojo_bindgen.ir import Unit
from mojo_bindgen.passes.normalize_type_refs import NormalizeTypeRefsPass
from mojo_bindgen.passes.resolve_decl_refs import ResolveDeclRefsPass
from mojo_bindgen.passes.validate_ir import ValidateIRPass


def run_ir_passes(unit: Unit) -> Unit:
    """Run the configured Unit-to-Unit pass pipeline."""
    current = unit
    for ir_pass in (
        NormalizeTypeRefsPass(),
        ResolveDeclRefsPass(),
        ValidateIRPass(),
    ):
        current = ir_pass.run(current)
    return current
