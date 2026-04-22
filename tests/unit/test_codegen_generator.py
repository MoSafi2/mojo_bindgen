"""Tests for the public MojoGenerator orchestration path."""

from __future__ import annotations

import mojo_bindgen.codegen.generator as generator_mod
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
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


def test_mojo_generator_lower_runs_ir_passes_then_lower(monkeypatch) -> None:
    unit = _demo_unit()
    normalized = _demo_unit()
    lowered = MojoModule(
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

    monkeypatch.setattr(generator_mod, "run_ir_passes", fake_run_ir_passes)
    monkeypatch.setattr(generator_mod, "lower_unit", fake_lower_unit)

    result = generator_mod.MojoGenerator(MojoEmitOptions()).lower(unit)

    assert result is lowered
    assert calls == [
        ("run_ir_passes", unit),
        ("lower_unit", normalized, MojoEmitOptions()),
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
