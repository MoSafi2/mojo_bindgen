"""Analysis-owned orchestration from raw CIR to finalized MojoIR."""

from __future__ import annotations

from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.normalize_mojo_module import (
    normalize_mojo_module,
)
from mojo_bindgen.analysis.pipeline import run_ir_passes
from mojo_bindgen.analysis.record_policies import assign_record_policies
from mojo_bindgen.analysis.unit_lowering import lower_unit
from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions, render_mojo_module
from mojo_bindgen.ir import Unit
from mojo_bindgen.mojo_ir import MojoModule


class AnalysisOrchestrator:
    """Own the full raw-CIR -> finalized-MojoIR pipeline."""

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        self._options = options or MojoEmitOptions()

    @property
    def options(self) -> MojoEmitOptions:
        return self._options

    def analyze(self, unit: Unit) -> MojoModule:
        current = run_ir_passes(unit)
        current = lower_unit(current, options=self._options)
        current = assign_record_policies(current)
        return normalize_mojo_module(current)


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

    def render(self, module: MojoModule) -> str:
        return render_mojo_module(
            module,
            MojoIRPrintOptions(module_comment=self._options.module_comment),
        )

    def generate(self, unit: Unit) -> str:
        return self.render(self.lower(unit))


def generate_mojo(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Generate Mojo source from raw CIR in one convenience call."""

    return MojoGenerator(options).generate(unit)


__all__ = [
    "AnalysisOrchestrator",
    "MojoGenerator",
    "analyze_to_mojo_module",
    "generate_mojo",
    "normalize_mojo_module",
]
