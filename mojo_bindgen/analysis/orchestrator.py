"""Analysis-owned orchestration from raw CIR to finalized MojoIR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.cir_canonicalizer import CIRCanonicalizer
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen.analysis.reachability import ReachabilityMaterializePass
from mojo_bindgen.analysis.record_policies import assign_record_policies
from mojo_bindgen.analysis.unit_lowering import lower_unit
from mojo_bindgen.analysis.validate_ir import ValidateIRPass
from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions, render_mojo_module
from mojo_bindgen.ir import Unit
from mojo_bindgen.layout_tests import render_layout_test_module
from mojo_bindgen.mojo_ir import MojoModule


@dataclass(frozen=True)
class AnalysisResult:
    normalized_unit: Unit
    mojo_module: MojoModule


@dataclass(frozen=True)
class GeneratedArtifacts:
    bindings_source: str
    layout_test_source: str | None = None


class AnalysisOrchestrator:
    """Own the full raw-CIR -> finalized-MojoIR pipeline."""

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


def analyze_to_mojo_module(unit: Unit, *, options: MojoEmitOptions | None = None) -> MojoModule:
    """Analyze raw CIR and return finalized printer-ready MojoIR."""

    return AnalysisOrchestrator(options).analyze(unit)


class MojoGenerator:
    """Compatibility facade that delegates lowering to analysis and printing to codegen."""

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        self._options = options or MojoEmitOptions()
        self._orchestrator = AnalysisOrchestrator(self._options)

    @property
    def options(self) -> MojoEmitOptions:
        return self._options

    def lower(self, unit: Unit) -> MojoModule:
        return self._orchestrator.analyze(unit)

    def analyze(self, unit: Unit) -> MojoModule:
        return self.lower(unit)

    def analyze_with_artifacts(self, unit: Unit) -> AnalysisResult:
        return self._orchestrator.analyze_with_artifacts(unit)

    def render(self, module: MojoModule) -> str:
        return render_mojo_module(
            module,
            MojoIRPrintOptions(module_comment=self._options.module_comment),
        )

    def generate(self, unit: Unit) -> str:
        return self.generate_artifacts(unit).bindings_source

    def generate_artifacts(
        self,
        unit: Unit,
        *,
        layout_tests: bool = False,
        main_module_name: str | None = None,
    ) -> GeneratedArtifacts:
        analysis = self.analyze_with_artifacts(unit)
        bindings_source = render_mojo_module(
            analysis.mojo_module,
            MojoIRPrintOptions(
                module_comment=self._options.module_comment,
            ),
        )
        layout_test_source = None
        if layout_tests:
            module_name = main_module_name or analysis.mojo_module.library
            layout_test_source = render_layout_test_module(
                normalized_unit=analysis.normalized_unit,
                mojo_module=analysis.mojo_module,
                main_module_name=module_name,
            )
        return GeneratedArtifacts(
            bindings_source=bindings_source,
            layout_test_source=layout_test_source,
        )


def generate_mojo(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Generate Mojo source from raw CIR in one convenience call."""

    return MojoGenerator(options).generate(unit)


def generate_mojo_artifacts(
    unit: Unit,
    options: MojoEmitOptions | None = None,
    *,
    layout_tests: bool = False,
    main_module_name: str | None = None,
) -> GeneratedArtifacts:
    """Generate Mojo source and optional companion artifacts from raw CIR."""

    return MojoGenerator(options).generate_artifacts(
        unit,
        layout_tests=layout_tests,
        main_module_name=main_module_name,
    )


__all__ = [
    "AnalysisResult",
    "AnalysisOrchestrator",
    "GeneratedArtifacts",
    "MojoGenerator",
    "analyze_to_mojo_module",
    "generate_mojo",
    "generate_mojo_artifacts",
    "normalize_mojo_module",
    "run_ir_passes",
]
