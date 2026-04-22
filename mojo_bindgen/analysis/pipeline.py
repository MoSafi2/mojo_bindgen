"""Orchestrate the Unit-to-Unit IR pass pipeline."""

from __future__ import annotations

from mojo_bindgen.ir import Unit
from mojo_bindgen.new_analysis.reachability import ReachabilityMaterializePass
from mojo_bindgen.new_analysis.validate_ir import ValidateIRPass


def run_ir_passes(unit: Unit) -> Unit:
    """Run the configured Unit-to-Unit pass pipeline."""
    current = ValidateIRPass().run(unit)
    current = ReachabilityMaterializePass().run(current).unit
    return current
