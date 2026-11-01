"""Test-only adapters for shared header acceptance; native work stays native.

Python IR classes are assertion views for this first migration. Native parsing,
codecs, analysis and emission execute in compiled drivers; decoding their debug
JSON here does not run Python's generator algorithms.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import pytest

from mojo_bindgen.analysis.mojo.mojo_emit_options import LinkingMode, MojoEmitOptions
from mojo_bindgen.ir import CConstExpr, Unit
from mojo_bindgen.serde import decode_c_expr, decode_cir, dumps_cir, loads_cir, to_debug_dict

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "mojo/pixi.toml"
NATIVE_PREFIX = ROOT / "mojo/.pixi/envs/default"


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
            [sys.executable, "-m", "mojo_bindgen.cli", *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=120,
        )


@dataclass
class NativeTools:
    """Session-owned executable builds, cached by source and optimization only."""

    directory: Path
    binaries: dict[tuple[str, int], Path] = field(default_factory=dict)

    def binary(self, kind: str, optimization: int) -> Path:
        key = (kind, optimization)
        if key not in self.binaries:
            source = (
                ROOT / "mojo/main.mojo"
                if kind == "cli"
                else ROOT / "tests/mojo/drivers/backend_driver.mojo"
            )
            target = self.directory / f"{kind}-O{optimization}"
            completed = subprocess.run(
                [
                    "pixi",
                    "run",
                    "--manifest-path",
                    str(MANIFEST),
                    "--locked",
                    "mojo",
                    "build",
                    "--Werror",
                    f"-O{optimization}",
                    "-I",
                    str(ROOT / "mojo"),
                    str(source),
                    "-o",
                    str(target),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=240,
            )
            if completed.returncode:
                raise HarnessError(completed.stdout + completed.stderr)
            self.binaries[key] = target
        return self.binaries[key]


@dataclass
class NativeHeaderHarness(HeaderGeneration):
    name: str
    optimization: int
    tools: NativeTools
    directory: Path
    environment: dict[str, str] = field(repr=False)

    def request(self, payload: dict) -> dict:
        path = self.directory / "request.json"
        path.write_text(json.dumps([payload]), encoding="utf-8")
        completed = subprocess.run(
            [str(self.tools.binary("backend", self.optimization)), str(path)],
            cwd=ROOT,
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=120,
        )
        if completed.returncode:
            raise HarnessError(completed.stdout + completed.stderr)
        lines = completed.stdout.splitlines()
        if len(lines) != 1:
            raise HarnessError("expected one native driver response: " + completed.stdout)
        result = json.loads(lines[0])
        if "error" in result:
            message = result["error"]
            if message.startswith("libclang reported errors parsing "):
                raise HeaderParseError(message)
            raise HarnessError(message)
        return result

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
        # The Python parser's optional scratch directory only affects its probe
        # files. Native Clang fallback uses unsaved input and creates no files.
        return decode_cir(
            self.request(
                {
                    "action": "parse-header",
                    "header": str(header),
                    "library": library,
                    "link_name": link_name,
                    "compile_args": compile_args,
                    "include_headers": [str(path) for path in include_headers or ()],
                    "clang_macro_fallback": clang_macro_fallback,
                }
            )["unit"]
        )

    def fold_expr(self, expr: CConstExpr) -> CConstExpr:
        return decode_c_expr(self.request({"action": "fold", "expr": to_debug_dict(expr)})["expr"])

    def expand_macros(
        self,
        tokens: list[str],
        environment: dict[str, list[str]],
        *,
        max_expansion_steps: int = 10000,
    ) -> list[str]:
        return self.request(
            {
                "action": "expand-macros",
                "tokens": tokens,
                "environment": environment,
                "max_expansion_steps": max_expansion_steps,
            }
        )["tokens"]

    def macro_environment(
        self, header: Path, *, library: str, link_name: str
    ) -> dict[str, list[str]]:
        return self.request(
            {
                "action": "macro-environment",
                "header": str(header),
                "library": library,
                "link_name": link_name,
            }
        )["environment"]

    def generate(self, unit: Unit, options: MojoEmitOptions | None = None) -> str:
        settings = options or MojoEmitOptions()
        payload = {
            "action": "generate",
            "unit": to_debug_dict(unit),
            "linking": settings.linking,
            "strict_abi": settings.strict_abi,
            "module_comment": settings.module_comment,
            "emit_doc_comments": settings.emit_doc_comments,
            "warn_abi": settings.warn_abi,
            "ffi_origin": settings.ffi_origin,
        }
        if settings.library_path_hint is not None:
            payload["library_path_hint"] = settings.library_path_hint
        return self.request(payload)["bindings"]

    def roundtrip_cir(self, unit: Unit) -> Unit:
        return decode_cir(
            self.request({"action": "roundtrip-cir", "unit": to_debug_dict(unit)})["unit"]
        )

    def run_cli(
        self, arguments: list[str], *, cwd: Path = ROOT
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.tools.binary("cli", self.optimization)), *arguments],
            cwd=cwd,
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=120,
        )


def native_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["CONDA_PREFIX"] = str(NATIVE_PREFIX)
    env["MOJO_BINDGEN_CLANG_LIBRARY_PATH"] = str(NATIVE_PREFIX / "lib/libclang.so")
    env["LD_LIBRARY_PATH"] = (
        str(NATIVE_PREFIX / "lib") + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    )
    # Keep compiler-probe PATH aligned with the Python harness. Only the generator
    # subprocess gets nightly runtime libraries; generated code uses the stable SDK.
    return env


@pytest.fixture(scope="session")
def native_header_tools(tmp_path_factory) -> NativeTools:
    return NativeTools(tmp_path_factory.mktemp("shared-native-tools"))


@pytest.fixture(scope="session")
def bindgen(request, tmp_path_factory) -> HeaderHarness:
    if request.param == "python":
        pytest.importorskip("clang.cindex")
        return PythonHeaderHarness()
    if not (NATIVE_PREFIX / "bin/mojo").is_file():
        message = "native toolchain missing: pixi install --manifest-path mojo/pixi.toml --locked"
        if request.config.getoption("--bindgen") == "native":
            pytest.fail(message)
        pytest.skip(message)
    optimization = 0 if request.param == "native-O0" else 3
    return NativeHeaderHarness(
        request.param,
        optimization,
        request.getfixturevalue("native_header_tools"),
        tmp_path_factory.mktemp(request.param),
        native_environment(),
    )
