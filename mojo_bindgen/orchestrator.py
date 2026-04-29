"""Top-level bindgen orchestrator for parsing, analysis, and code generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.orchestrator import AnalysisOrchestrator
from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions, render_mojo_module
from mojo_bindgen.ir import Unit
from mojo_bindgen.layout_tests import render_layout_test_module
from mojo_bindgen.mojo_ir import MojoModule
from mojo_bindgen.parsing.parser import ClangParser

LinkingMode = Literal["external_call", "owned_dl_handle"]


@dataclass(frozen=True)
class BindgenOptions:
    header: Path
    library: str | None = None
    link_name: str | None = None
    compile_args: list[str] | None = None
    linking: LinkingMode = "external_call"
    library_path_hint: str | None = None
    strict_abi: bool = False
    module_comment: bool = True
    layout_tests: bool | None = None
    json_output: bool = False
    output: Path | None = None
    layout_test_output: Path | None = None


@dataclass(frozen=True)
class RenderedArtifacts:
    bindings_source: str
    layout_test_source: str | None = None


@dataclass(frozen=True)
class BindgenResult:
    unit: Unit
    mojo_module: MojoModule
    bindings_source: str
    layout_test_source: str | None = None


class BindgenOrchestrator:
    """Own the user-facing bindgen pipeline and output decisions."""

    def __init__(self, options: BindgenOptions) -> None:
        self._options = options

    @property
    def options(self) -> BindgenOptions:
        return self._options

    @property
    def emit_options(self) -> MojoEmitOptions:
        return MojoEmitOptions(
            linking=self._options.linking,
            library_path_hint=self._options.library_path_hint,
            strict_abi=self._options.strict_abi,
            module_comment=self._options.module_comment,
        )

    def parse(self) -> Unit:
        header = self._options.header
        library_name = self._library_name()
        link_name = self._link_name(library_name)
        parser = ClangParser(
            header,
            library=library_name,
            link_name=link_name,
            compile_args=self._options.compile_args,
            raise_on_error=True,
        )
        return parser.run()

    def analyze(self, unit: Unit) -> MojoModule:
        return AnalysisOrchestrator(self.emit_options).analyze(unit)

    def codegen(
        self,
        unit_or_module: Unit | MojoModule,
        *,
        normalized_unit: Unit | None = None,
    ) -> RenderedArtifacts:
        if isinstance(unit_or_module, Unit):
            analysis = AnalysisOrchestrator(self.emit_options).analyze_with_artifacts(
                unit_or_module
            )
            return self._render_artifacts(
                analysis.mojo_module,
                normalized_unit=analysis.normalized_unit,
            )

        return self._render_artifacts(
            unit_or_module,
            normalized_unit=normalized_unit,
        )

    def run(self) -> BindgenResult:
        unit = self.parse()
        analysis = AnalysisOrchestrator(self.emit_options).analyze_with_artifacts(unit)
        rendered = self.codegen(
            analysis.mojo_module,
            normalized_unit=analysis.normalized_unit,
        )
        return BindgenResult(
            unit=unit,
            mojo_module=analysis.mojo_module,
            bindings_source=rendered.bindings_source,
            layout_test_source=rendered.layout_test_source,
        )

    def _render_artifacts(
        self,
        module: MojoModule,
        *,
        normalized_unit: Unit | None,
    ) -> RenderedArtifacts:
        bindings_source = render_mojo_module(
            module,
            MojoIRPrintOptions(module_comment=self._options.module_comment),
        )
        layout_test_source = None
        if self._should_emit_layout_tests() and normalized_unit is not None:
            layout_test_source = render_layout_test_module(
                normalized_unit=normalized_unit,
                mojo_module=module,
                main_module_name=self._layout_test_module_name(),
            )
        return RenderedArtifacts(
            bindings_source=bindings_source,
            layout_test_source=layout_test_source,
        )

    def _should_emit_layout_tests(self) -> bool:
        if self._options.json_output:
            return False
        if self._options.layout_test_output is not None:
            return self._options.layout_tests is not False
        if self._options.output is None:
            return False
        if self._options.layout_tests is None:
            return True
        return self._options.layout_tests

    def _layout_test_module_name(self) -> str:
        if self._options.output is not None:
            return self._options.output.stem
        return self._header_stem()

    def _header_stem(self) -> str:
        header = self._options.header
        return header.stem if header.suffix else str(header)

    def _library_name(self) -> str:
        return self._options.library if self._options.library is not None else self._header_stem()

    def _link_name(self, library_name: str) -> str:
        return self._options.link_name if self._options.link_name is not None else library_name


def bindgen(options: BindgenOptions) -> BindgenResult:
    return BindgenOrchestrator(options).run()


__all__ = [
    "BindgenOptions",
    "BindgenOrchestrator",
    "BindgenResult",
    "bindgen",
]
