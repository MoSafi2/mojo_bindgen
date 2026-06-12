"""Analysis pipeline from raw CIR to finalized MojoIR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.cir_canonicalizer import CIRCanonicalizer
from mojo_bindgen.analysis.context import AnalysisContext, build_analysis_context
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.reachability import SignatureRecordStubPass
from mojo_bindgen.analysis.record_policies import assign_record_policies
from mojo_bindgen.analysis.reference_validation import ValidateReferencesPass
from mojo_bindgen.analysis.unit_lowering import lower_unit
from mojo_bindgen.analysis.validate_ir import ValidateIRPass
from mojo_bindgen.codegen.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen.ir import MojoModule, Unit


@dataclass(frozen=True)
class AnalysisResult:
    normalized_unit: Unit
    mojo_module: MojoModule


@dataclass(frozen=True)
class AnalysisArtifacts:
    """Artifacts produced by the staged analysis pipeline."""

    raw_unit: Unit
    validated_unit: Unit
    normalized_unit: Unit
    context: AnalysisContext
    policy_light_module: MojoModule
    mojo_module: MojoModule


class AnalysisOrchestrator:
    """Own the raw-CIR -> finalized-MojoIR analysis pipeline."""

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        self._options = options or MojoEmitOptions()

    @property
    def options(self) -> MojoEmitOptions:
        return self._options

    def normalize_cir(self, unit: Unit) -> Unit:
        """Run the ordered, pure CIR repair sequence before MojoIR lowering."""
        validated = ValidateIRPass().run(unit)
        with_signature_stubs = SignatureRecordStubPass().run(validated).unit
        normalized = CIRCanonicalizer().canonicalize(with_signature_stubs)
        normalized = ValidateIRPass().run(normalized)
        return ValidateReferencesPass().run(normalized)

    def run_ir_passes(self, unit: Unit) -> Unit:
        """Compatibility alias for the CIR normalization pass sequence."""
        return self.normalize_cir(unit)

    def lower_normalized(
        self,
        unit: Unit,
        *,
        context: AnalysisContext | None = None,
    ) -> MojoModule:
        """Lower already-normalized CIR into policy-free MojoIR."""
        return lower_unit(unit, options=self._options, context=context)

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
        artifacts = self.analyze_pipeline(unit)
        return AnalysisResult(
            normalized_unit=artifacts.normalized_unit,
            mojo_module=artifacts.mojo_module,
        )

    def analyze_pipeline(self, unit: Unit) -> AnalysisArtifacts:
        """Run the full analysis pipeline and return all major stage artifacts."""
        validated_unit = ValidateIRPass().run(unit)
        with_signature_stubs = SignatureRecordStubPass().run(validated_unit).unit
        normalized_unit = ValidateIRPass().run(
            CIRCanonicalizer().canonicalize(with_signature_stubs)
        )
        normalized_unit = ValidateReferencesPass().run(normalized_unit)
        context = build_analysis_context(normalized_unit)
        lowered = self.lower_normalized(normalized_unit, context=context)
        return AnalysisArtifacts(
            raw_unit=unit,
            validated_unit=validated_unit,
            normalized_unit=normalized_unit,
            context=context,
            policy_light_module=lowered,
            mojo_module=self.finalize(lowered),
        )


def run_ir_passes(unit: Unit) -> Unit:
    """Run the analysis-owned CIR pass sequence before MojoIR lowering."""
    return AnalysisOrchestrator().run_ir_passes(unit)


__all__ = [
    "AnalysisResult",
    "AnalysisArtifacts",
    "AnalysisOrchestrator",
    "run_ir_passes",
]
