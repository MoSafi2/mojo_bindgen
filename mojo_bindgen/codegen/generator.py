"""Public orchestration API for Mojo code generation.

Higher-level callers should use :class:`MojoGenerator` rather than stitching
analysis and rendering together manually.
"""

from __future__ import annotations

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.render import MojoRenderer
from mojo_bindgen.ir import Unit
from mojo_bindgen.passes import AnalyzeForMojoPass, run_ir_passes
from mojo_bindgen.passes.analyze_for_mojo import AnalyzedUnit


class MojoGenerator:
    """Orchestrate analysis and rendering for Mojo bindings.

    The generator owns a stable codegen interface for callers that want either
    one-shot generation or explicit access to intermediate analysis results.
    """

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        """Store the codegen options used for all subsequent operations."""
        self._options = options or MojoEmitOptions()

    @property
    def options(self) -> MojoEmitOptions:
        """Return the options currently bound to this generator."""
        return self._options

    def analyze(self, unit: Unit) -> AnalyzedUnit:
        """Run semantic codegen analysis over ``unit``."""
        normalized = run_ir_passes(unit)
        return AnalyzeForMojoPass(self._options).run(normalized)

    def render(self, analyzed: AnalyzedUnit) -> str:
        """Render previously analyzed codegen state to Mojo source."""
        return MojoRenderer(analyzed).render()

    def generate(self, unit: Unit) -> str:
        """Analyze and render ``unit`` in one step."""
        return self.render(self.analyze(unit))


def generate_mojo(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Generate a Mojo module from parsed IR in one convenience call."""
    return MojoGenerator(options).generate(unit)
