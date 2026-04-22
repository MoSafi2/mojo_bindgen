"""Public orchestration API for Mojo code generation.

Higher-level callers should use :class:`MojoGenerator` rather than stitching
lowering, normalization, and rendering together manually.
"""

from __future__ import annotations

from mojo_bindgen.analysis import lower_unit, run_ir_passes
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions, render_mojo_module
from mojo_bindgen.ir import Unit
from mojo_bindgen.mojo_ir import MojoModule


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

    def lower(self, unit: Unit) -> MojoModule:
        """Run CIR passes and lower ``unit`` into standalone MojoIR."""
        normalized = run_ir_passes(unit)
        return lower_unit(normalized, options=self._options)

    def analyze(self, unit: Unit) -> MojoModule:
        """Compatibility wrapper for callers that previously asked for an intermediate model."""
        return self.lower(unit)

    def render(self, module: MojoModule) -> str:
        """Render previously lowered MojoIR to Mojo source."""
        return render_mojo_module(
            module,
            MojoIRPrintOptions(module_comment=self._options.module_comment),
        )

    def generate(self, unit: Unit) -> str:
        """Lower and render ``unit`` in one step."""
        return self.render(self.lower(unit))


def generate_mojo(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Generate a Mojo module from parsed IR in one convenience call."""
    return MojoGenerator(options).generate(unit)
