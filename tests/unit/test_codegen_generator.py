"""Tests for the public analysis-owned MojoGenerator orchestration path."""

from __future__ import annotations

import mojo_bindgen.analysis.orchestrator as generator_mod
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import Function, IntKind, IntType, TargetABI, Unit, VoidType
from mojo_bindgen.mojo_ir import LinkMode, MojoModule


def _abi() -> TargetABI:
    return TargetABI(pointer_size_bytes=8, pointer_align_bytes=8)


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


def test_mojo_generator_lower_uses_analysis_orchestrator(monkeypatch) -> None:
    unit = _demo_unit()
    lowered = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )
    captured: dict[str, object] = {}

    class DummyOrchestrator:
        def __init__(self, options) -> None:
            captured["options"] = options

        def analyze(self, arg):
            captured["unit"] = arg
            return lowered

    monkeypatch.setattr(generator_mod, "AnalysisOrchestrator", DummyOrchestrator)

    result = generator_mod.MojoGenerator(MojoEmitOptions()).lower(unit)

    assert result is lowered
    assert captured == {
        "options": MojoEmitOptions(),
        "unit": unit,
    }


def test_analysis_orchestrator_runs_full_analysis_sequence(monkeypatch) -> None:
    unit = _demo_unit()
    normalized = _demo_unit()
    lowered = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )
    policy_applied = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )
    normalized_module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )
    calls: list[tuple[str, object]] = []

    def fake_run_ir_passes(arg):
        calls.append(("run_ir_passes", arg))
        return normalized

    def fake_lower_unit(arg, *, options):
        calls.append(("lower_unit", arg, options))
        return lowered

    def fake_assign_record_policies(arg):
        calls.append(("assign_record_policies", arg))
        return policy_applied

    def fake_normalize_mojo_module(arg):
        calls.append(("normalize", arg))
        return normalized_module

    monkeypatch.setattr(generator_mod, "run_ir_passes", fake_run_ir_passes)
    monkeypatch.setattr(generator_mod, "lower_unit", fake_lower_unit)
    monkeypatch.setattr(generator_mod, "assign_record_policies", fake_assign_record_policies)
    monkeypatch.setattr(generator_mod, "normalize_mojo_module", fake_normalize_mojo_module)

    result = generator_mod.AnalysisOrchestrator(MojoEmitOptions()).analyze(unit)

    assert result is normalized_module
    assert calls == [
        ("run_ir_passes", unit),
        ("lower_unit", normalized, MojoEmitOptions()),
        ("assign_record_policies", lowered),
        ("normalize", policy_applied),
    ]


def test_mojo_generator_render_passes_module_comment_to_printer(monkeypatch) -> None:
    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode=LinkMode.EXTERNAL_CALL,
    )
    captured: dict[str, object] = {}

    def fake_render_mojo_module(arg, options):
        captured["module"] = arg
        captured["module_comment"] = options.module_comment
        return "generated"

    monkeypatch.setattr(generator_mod, "render_mojo_module", fake_render_mojo_module)

    result = generator_mod.MojoGenerator(MojoEmitOptions(module_comment=False)).render(module)

    assert result == "generated"
    assert captured == {
        "module": module,
        "module_comment": False,
    }


def test_mojo_generator_ignores_strict_abi_in_default_pipeline() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Function(
                decl_id="fn:add",
                name="add",
                link_name="add",
                ret=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                params=[],
            )
        ],
    )

    default_out = generator_mod.MojoGenerator(MojoEmitOptions()).generate(unit)
    strict_out = generator_mod.MojoGenerator(MojoEmitOptions(strict_abi=True)).generate(unit)

    assert strict_out == default_out
