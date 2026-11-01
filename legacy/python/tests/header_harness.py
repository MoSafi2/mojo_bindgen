"""Python reference adapter for behavior tests retained during coexistence.

Native acceptance and assertions live independently under tests/mojo.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

import pytest

from mojo_bindgen.analysis.mojo.mojo_emit_options import LinkingMode, MojoEmitOptions
from mojo_bindgen.codegen.mojo_ir_printer import MojoIRPrintOptions
from mojo_bindgen.ir import CConstExpr, MojoConstExpr, MojoModule, TargetABI, Unit
from mojo_bindgen.layout_tests import LayoutRecordCheck
from mojo_bindgen.serde import (
    decode_cir,
    decode_mojo_ir,
    dumps_cir,
    loads_cir,
)
from tests._paths import ROOT as _SHARED_ROOT

ROOT = _SHARED_ROOT


class HeaderParseError(RuntimeError):
    """Clang reported source errors; distinct from driver/toolchain failures."""


class HarnessError(RuntimeError):
    """A generator or its test transport failed."""


class HeaderHarness(Protocol):
    name: str

    def parse_header(
        self,
        header: Path,
        *,
        library: str,
        link_name: str,
        compile_args: list[str] | None = None,
        include_headers: list[Path] | None = None,
        clang_macro_fallback: bool = False,
        clang_macro_fallback_build_dir: Path | None = None,
    ) -> Unit: ...

    def decode_debug_ir(
        self, payload: object, *, stage: Literal["cir", "mojo"]
    ) -> Unit | MojoModule: ...

    def map_expr(self, expr: CConstExpr, *, target_abi: TargetABI) -> MojoConstExpr: ...

    def map_unit(self, unit: Unit, *, options: MojoEmitOptions | None = None) -> MojoModule: ...

    def analyze(self, unit: Unit) -> MojoModule: ...

    def normalize(self, module: MojoModule) -> MojoModule: ...

    def render(self, module: MojoModule, options: MojoIRPrintOptions | None = None) -> str: ...

    def layout_checks(
        self, *, normalized_unit: Unit, mojo_module: MojoModule
    ) -> tuple[LayoutRecordCheck, ...]: ...

    def render_layout(
        self, *, normalized_unit: Unit, mojo_module: MojoModule, main_module_name: str
    ) -> str: ...

    def fold_expr(self, expr: CConstExpr) -> CConstExpr: ...

    def expand_macros(
        self,
        tokens: list[str],
        environment: dict[str, list[str]],
        *,
        max_expansion_steps: int = 10000,
    ) -> list[str]: ...

    def macro_environment(
        self, header: Path, *, library: str, link_name: str
    ) -> dict[str, list[str]]: ...

    def generate(self, unit: Unit, options: MojoEmitOptions | None = None) -> str: ...

    def roundtrip_cir(self, unit: Unit) -> Unit: ...

    def run_cli(
        self, arguments: list[str], *, cwd: Path = ROOT
    ) -> subprocess.CompletedProcess[str]: ...

    def generate_header(
        self,
        header: Path,
        *,
        library: str,
        link_name: str,
        linking: LinkingMode = "external_call",
        library_path_hint: str | None = None,
    ) -> str: ...


class HeaderGeneration:
    """Common CLI invocation shape; concrete adapters choose the executable."""

    def run_cli(
        self, arguments: list[str], *, cwd: Path = ROOT
    ) -> subprocess.CompletedProcess[str]:
        raise NotImplementedError

    def generate_header(
        self,
        header: Path,
        *,
        library: str,
        link_name: str,
        linking: LinkingMode = "external_call",
        library_path_hint: str | None = None,
    ) -> str:
        arguments = [
            str(header),
            "--library",
            library,
            "--link-name",
            link_name,
            "--link-mode",
            linking.replace("_", "-"),
        ]
        if library_path_hint is not None:
            arguments += ["--library-path", library_path_hint]
        completed = self.run_cli(arguments)
        if completed.returncode:
            raise HarnessError(completed.stdout + completed.stderr)
        return completed.stdout


@dataclass
class PythonHeaderHarness(HeaderGeneration):
    name: str = field(default="python", init=False)

    def parse_header(
        self,
        header: Path,
        *,
        library: str,
        link_name: str,
        compile_args: list[str] | None = None,
        include_headers: list[Path] | None = None,
        clang_macro_fallback: bool = False,
        clang_macro_fallback_build_dir: Path | None = None,
    ) -> Unit:
        from mojo_bindgen.parsing.parser import ClangParser, ParseError

        try:
            return ClangParser(
                header,
                library=library,
                link_name=link_name,
                compile_args=compile_args,
                include_headers=include_headers,
                clang_macro_fallback=clang_macro_fallback,
                clang_macro_fallback_build_dir=clang_macro_fallback_build_dir,
            ).run()
        except ParseError as error:
            raise HeaderParseError(str(error)) from error

    def decode_debug_ir(
        self, payload: object, *, stage: Literal["cir", "mojo"]
    ) -> Unit | MojoModule:
        try:
            return decode_cir(payload) if stage == "cir" else decode_mojo_ir(payload)
        except (ValueError, TypeError) as error:
            raise HarnessError(str(error)) from error

    def map_expr(self, expr: CConstExpr, *, target_abi: TargetABI) -> MojoConstExpr:
        from mojo_bindgen.analysis.facts.target import TargetQueries
        from mojo_bindgen.analysis.mojo.const_expr_mapping import (
            ConstExprMappingError,
            map_const_expr,
        )
        from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass

        try:
            return map_const_expr(expr, type_mapper=MapTypePass(queries=TargetQueries(target_abi)))
        except ConstExprMappingError as error:
            raise HarnessError(str(error)) from error

    def map_unit(self, unit: Unit, *, options: MojoEmitOptions | None = None) -> MojoModule:
        from mojo_bindgen.analysis import map_unit

        return map_unit(unit, options=options)

    def analyze(self, unit: Unit) -> MojoModule:
        from tests.bindgen_helpers import analyze_to_mojo_module

        return analyze_to_mojo_module(unit)

    def normalize(self, module: MojoModule) -> MojoModule:
        from mojo_bindgen.codegen.normalize_mojo_module import normalize_mojo_module

        return normalize_mojo_module(module)

    def render(self, module: MojoModule, options: MojoIRPrintOptions | None = None) -> str:
        from mojo_bindgen.codegen.mojo_ir_printer import render_mojo_module

        return render_mojo_module(module, options)

    def layout_checks(
        self, *, normalized_unit: Unit, mojo_module: MojoModule
    ) -> tuple[LayoutRecordCheck, ...]:
        from mojo_bindgen.layout_tests import collect_layout_record_checks

        return collect_layout_record_checks(
            normalized_unit=normalized_unit, mojo_module=mojo_module
        )

    def render_layout(
        self, *, normalized_unit: Unit, mojo_module: MojoModule, main_module_name: str
    ) -> str:
        from mojo_bindgen.layout_tests import render_layout_test_module

        return render_layout_test_module(
            normalized_unit=normalized_unit,
            mojo_module=mojo_module,
            main_module_name=main_module_name,
        )

    def fold_expr(self, expr: CConstExpr) -> CConstExpr:
        from mojo_bindgen.parsing.lowering.const_expr import fold_const_expr

        return fold_const_expr(expr)

    def expand_macros(
        self,
        tokens: list[str],
        environment: dict[str, list[str]],
        *,
        max_expansion_steps: int = 10000,
    ) -> list[str]:
        from mojo_bindgen.parsing.lowering.macro_env import expand_object_like_macro_tokens

        return expand_object_like_macro_tokens(
            tokens, environment, max_expansion_steps=max_expansion_steps
        )

    def macro_environment(
        self, header: Path, *, library: str, link_name: str
    ) -> dict[str, list[str]]:
        from mojo_bindgen.parsing.lowering.macro_env import collect_object_like_macro_env
        from mojo_bindgen.parsing.parser import ClangParser

        session = ClangParser(header, library=library, link_name=link_name)._build_parser_session()
        return collect_object_like_macro_env(session.tu)

    def generate(self, unit: Unit, options: MojoEmitOptions | None = None) -> str:
        from tests.bindgen_helpers import render_mojo_source

        return render_mojo_source(unit, options)

    def roundtrip_cir(self, unit: Unit) -> Unit:
        return loads_cir(dumps_cir(unit))

    def run_cli(
        self, arguments: list[str], *, cwd: Path = ROOT
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", "-m", "mojo_bindgen.cli", *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=120,
        )


@pytest.fixture(scope="session")
def bindgen() -> HeaderHarness:
    """Python reference lane; native acceptance lives in Mojo TestSuite programs."""
    pytest.importorskip("clang.cindex")
    return PythonHeaderHarness()
