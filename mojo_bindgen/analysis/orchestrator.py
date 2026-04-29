"""Analysis pipeline from raw CIR to finalized MojoIR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.cir_canonicalizer import CIRCanonicalizer
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.reachability import ReachabilityMaterializePass
from mojo_bindgen.analysis.record_policies import assign_record_policies
from mojo_bindgen.analysis.unit_lowering import lower_unit
from mojo_bindgen.analysis.validate_ir import ValidateIRPass
from mojo_bindgen.codegen.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen.ir import Unit
from mojo_bindgen.mojo_ir import MojoModule


@dataclass(frozen=True)
class AnalysisResult:
    normalized_unit: Unit
    mojo_module: MojoModule


class AnalysisOrchestrator:
    """Own the raw-CIR -> finalized-MojoIR analysis pipeline."""

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        self._options = options or MojoEmitOptions()

    @property
    def options(self) -> MojoEmitOptions:
        return self._options

    def normalize_cir(self, unit: Unit) -> Unit:
        """Run the CIR repair sequence before MojoIR lowering."""
        current = ValidateIRPass().run(unit)
        current = ReachabilityMaterializePass().run(current).unit
        current = CIRCanonicalizer().canonicalize(current)
        return current

    def run_ir_passes(self, unit: Unit) -> Unit:
        """Compatibility alias for the CIR normalization pass sequence."""
        return self.normalize_cir(unit)

    def lower_normalized(self, unit: Unit) -> MojoModule:
        """Lower already-normalized CIR into policy-free MojoIR."""
        return lower_unit(unit, options=self._options)

    def lower(self, unit: Unit) -> MojoModule:
        """Lower validated CIR into policy-free MojoIR."""
        return self.lower_normalized(self.normalize_cir(unit))

    def finalize(self, module: MojoModule) -> MojoModule:
        """Apply late record policy decisions and final normalization."""
        current = assign_record_policies(module)
        return normalize_mojo_module(current)

    def analyze(self, unit: Unit) -> MojoModule:
        return self.analyze_with_artifacts(unit).mojo_module

    def analyze_with_artifacts(self, unit: Unit) -> AnalysisResult:
        normalized_unit = self.run_ir_passes(unit)
        lowered = self.lower_normalized(normalized_unit)
        return AnalysisResult(
            normalized_unit=normalized_unit,
            mojo_module=self.finalize(lowered),
        )


def run_ir_passes(unit: Unit) -> Unit:
    """Run the analysis-owned CIR pass sequence before MojoIR lowering."""
    return AnalysisOrchestrator().run_ir_passes(unit)


__all__ = [
    "AnalysisResult",
    "AnalysisOrchestrator",
    "run_ir_passes",
]
