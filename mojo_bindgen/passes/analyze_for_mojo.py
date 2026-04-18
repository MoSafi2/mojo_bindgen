"""Final semantic analysis pass producing AnalyzedUnit."""

from __future__ import annotations

from mojo_bindgen.codegen.analysis import AnalyzedUnit, analyze_unit_semantics
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import Unit


class AnalyzeForMojoPass:
    """Produce final Mojo-specific analyzed output from normalized IR."""

    def __init__(self, options: MojoEmitOptions) -> None:
        self._options = options

    def run(self, unit: Unit) -> AnalyzedUnit:
        return analyze_unit_semantics(unit, self._options)
