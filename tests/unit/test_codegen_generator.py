"""Tests for the top-level bindgen orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import mojo_bindgen.orchestrator as orchestrator_mod
from mojo_bindgen import BindgenOptions, BindgenOrchestrator, bindgen
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import ByteOrder, Function, TargetABI, Unit, VoidType
from mojo_bindgen.mojo_ir import LinkMode, MojoModule


def _abi() -> TargetABI:
    return TargetABI(
        pointer_size_bytes=8,
        pointer_align_bytes=8,
        byte_order=ByteOrder.LITTLE,
    )


def _demo_unit() -> Unit:
    return Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Function(
                decl_id="fn:install",
                name="install",
                link_name="install",
                ret=VoidType(),
                params=[],
            )
        ],
    )


def _options_for_unit(unit: Unit, emit_options: MojoEmitOptions | None = None) -> BindgenOptions:
    options = emit_options or MojoEmitOptions()
    return BindgenOptions(
        header=Path(unit.source_header),
        library=unit.library,
        link_name=unit.link_name,
        linking=options.linking,
        library_path_hint=options.library_path_hint,
        strict_abi=options.strict_abi,
        module_comment=options.module_comment,
    )


def test_parse_builds_clang_parser(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class DummyParser:
        def __init__(
            self, header: Path, *, library: str, link_name: str, compile_args, raise_on_error
        ):
            calls["header"] = header
            calls["library"] = library
            calls["link_name"] = link_name
            calls["compile_args"] = compile_args
            calls["raise_on_error"] = raise_on_error

        def run(self) -> Unit:
            return _demo_unit()

    monkeypatch.setattr(orchestrator_mod, "ClangParser", DummyParser)

    options = BindgenOptions(
        header=Path("demo.h"),
        compile_args=["-I./include"],
    )
    result = BindgenOrchestrator(options).parse()

    assert result == _demo_unit()
    assert calls == {
        "header": Path("demo.h"),
        "library": "demo",
        "link_name": "demo",
        "compile_args": ["-I./include"],
        "raise_on_error": True,
    }


def test_analyze_uses_analysis_orchestrator(monkeypatch) -> None:
    unit = _demo_unit()
    lowered = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )
    captured: dict[str, object] = {}

    class DummyAnalysisOrchestrator:
        def __init__(self, options) -> None:
            captured["options"] = options

        def analyze(self, arg):
            captured["unit"] = arg
            return lowered

    monkeypatch.setattr(orchestrator_mod, "AnalysisOrchestrator", DummyAnalysisOrchestrator)

    result = BindgenOrchestrator(_options_for_unit(unit)).analyze(unit)

    assert result is lowered
    assert captured["unit"] is unit
    assert captured["options"] == MojoEmitOptions()


def test_codegen_renders_bindings_and_layout_tests(monkeypatch) -> None:
    unit = _demo_unit()
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )
    calls: dict[str, object] = {}

    def fake_render_mojo_module(arg, options):
        calls["module"] = arg
        calls["module_comment"] = options.module_comment
        return "generated"

    def fake_render_layout_test_module(*, normalized_unit, mojo_module, main_module_name):
        calls["normalized_unit"] = normalized_unit
        calls["layout_module"] = mojo_module
        calls["main_module_name"] = main_module_name
        return "layout"

    monkeypatch.setattr(orchestrator_mod, "render_mojo_module", fake_render_mojo_module)
    monkeypatch.setattr(
        orchestrator_mod, "render_layout_test_module", fake_render_layout_test_module
    )

    options = BindgenOptions(
        header=Path("demo.h"),
        output=Path("/tmp/demo_bindings.mojo"),
        layout_tests=True,
        module_comment=False,
    )
    artifacts = BindgenOrchestrator(options).codegen(module, normalized_unit=unit)

    assert artifacts.bindings_source == "generated"
    assert artifacts.layout_test_source == "layout"
    assert calls == {
        "module": module,
        "module_comment": False,
        "normalized_unit": unit,
        "layout_module": module,
        "main_module_name": "demo_bindings",
    }


def test_run_returns_full_result(monkeypatch) -> None:
    unit = _demo_unit()
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )

    @dataclass(frozen=True)
    class DummyAnalysisResult:
        normalized_unit: Unit
        mojo_module: MojoModule

    class DummyAnalysisOrchestrator:
        def __init__(self, _options) -> None:
            pass

        def analyze_with_artifacts(self, arg):
            assert arg == unit
            return DummyAnalysisResult(normalized_unit=unit, mojo_module=module)

    class DummyRendered:
        bindings_source = "generated"
        layout_test_source = None

    monkeypatch.setattr(orchestrator_mod, "AnalysisOrchestrator", DummyAnalysisOrchestrator)
    monkeypatch.setattr(
        BindgenOrchestrator,
        "parse",
        lambda self: unit,
    )
    monkeypatch.setattr(
        BindgenOrchestrator,
        "codegen",
        lambda self, _module, *, normalized_unit=None: DummyRendered(),
    )

    result = BindgenOrchestrator(_options_for_unit(unit)).run()

    assert result.unit is unit
    assert result.mojo_module is module
    assert result.bindings_source == "generated"
    assert result.layout_test_source is None


def test_bindgen_wrapper_uses_orchestrator(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyResult:
        unit = _demo_unit()
        mojo_module = MojoModule(
            source_header="demo.h",
            library="demo",
            link_name="demo",
            link_mode=LinkMode.EXTERNAL_CALL,
        )
        bindings_source = "generated"
        layout_test_source = None

    class DummyOrchestrator:
        def __init__(self, options) -> None:
            captured["options"] = options

        def run(self):
            return DummyResult()

    monkeypatch.setattr(orchestrator_mod, "BindgenOrchestrator", DummyOrchestrator)

    result = bindgen(_options_for_unit(_demo_unit()))

    assert result.bindings_source == "generated"
    assert captured["options"].header == Path("demo.h")
