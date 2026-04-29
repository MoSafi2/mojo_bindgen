"""Test helpers that adapt legacy generator-style assertions to the new orchestrator."""

from __future__ import annotations

from pathlib import Path

from mojo_bindgen import BindgenOptions, BindgenOrchestrator
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions, render_mojo_module
from mojo_bindgen.ir import Unit
from mojo_bindgen.mojo_ir import MojoModule


def _bindgen_options_from_emit_options(unit: Unit, options: MojoEmitOptions) -> BindgenOptions:
    return BindgenOptions(
        header=Path(unit.source_header),
        library=unit.library,
        link_name=unit.link_name,
        linking=options.linking,
        library_path_hint=options.library_path_hint,
        strict_abi=options.strict_abi,
        module_comment=options.module_comment,
    )


def render_mojo_source(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    emit_options = options or MojoEmitOptions()
    orchestrator = BindgenOrchestrator(_bindgen_options_from_emit_options(unit, emit_options))
    return orchestrator.codegen(unit).bindings_source


def analyze_to_mojo_module(unit: Unit, options: MojoEmitOptions | None = None) -> MojoModule:
    emit_options = options or MojoEmitOptions()
    orchestrator = BindgenOrchestrator(_bindgen_options_from_emit_options(unit, emit_options))
    return orchestrator.analyze(unit)


class MojoGenerator:
    """Legacy-shaped adapter for tests that still expect generator-style methods."""

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        self._options = options or MojoEmitOptions()

    @property
    def options(self) -> MojoEmitOptions:
        return self._options

    def lower(self, unit: Unit) -> MojoModule:
        return analyze_to_mojo_module(unit, self._options)

    def analyze(self, unit: Unit) -> MojoModule:
        return self.lower(unit)

    def render(self, module: MojoModule) -> str:
        return render_mojo_module(
            module,
            MojoIRPrintOptions(module_comment=self._options.module_comment),
        )

    def generate(self, unit: Unit) -> str:
        return render_mojo_source(unit, self._options)
