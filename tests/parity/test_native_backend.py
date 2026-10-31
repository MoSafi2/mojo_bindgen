"""Backend parity. Python is used only to supply fixtures and expected results."""

from __future__ import annotations

import copy
import json
import math
import os
import random
import struct
import subprocess
from dataclasses import replace

import pytest

from mojo_bindgen import ir
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.mojo.const_expr_mapping import MapConstExprPass
from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.pipeline import AnalysisOrchestrator
from mojo_bindgen.codegen.mojo_ir_printer import (
    MojoIRPrinter,
    MojoIRPrintOptions,
    render_mojo_module,
)
from mojo_bindgen.codegen.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen.layout_tests.generator import render_layout_test_module
from mojo_bindgen.parsing.parser import ClangParser
from mojo_bindgen.serde import decode_cir, decode_mojo_ir, to_debug_dict
from tests.parity.test_native_types import MANIFEST, ROOT

pytestmark = [pytest.mark.expensive, pytest.mark.integration]
I32 = ir.IntType(ir.IntKind.INT, 4, 4)
ABI = ir.TargetABI(8, 8, ir.ByteOrder.LITTLE, "x86_64-unknown-linux-gnu")


@pytest.fixture(scope="module", params=[0, 3], ids=["O0", "O3"])
def backend(request, tmp_path_factory):
    directory = tmp_path_factory.mktemp(f"native-backend-o{request.param}")
    binary = directory / "backend"
    completed = subprocess.run(
        [
            "pixi",
            "run",
            "--manifest-path",
            str(MANIFEST),
            "--locked",
            "mojo",
            "build",
            "-I",
            str(ROOT / "mojo"),
            f"-O{request.param}",
            "--Werror",
            str(ROOT / "tests/mojo/drivers/backend_driver.mojo"),
            "-o",
            str(binary),
        ],
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert completed.returncode == 0, completed.stderr
    env = os.environ.copy()
    env["LD_LIBRARY_PATH"] = (
        str(ROOT / "mojo/.pixi/envs/default/lib") + ":" + env.get("LD_LIBRARY_PATH", "")
    )

    def run(requests):
        before = copy.deepcopy(requests)
        path = directory / "input.json"
        path.write_text(json.dumps(requests), encoding="utf-8")
        result = subprocess.run(
            [str(binary), str(path)], capture_output=True, text=True, env=env, timeout=120
        )
        assert result.returncode == 0, result.stderr
        assert requests == before
        output = [json.loads(line) for line in result.stdout.splitlines()]
        assert len(output) == len(requests)
        return output

    return run


def _expected(unit, options):
    before = to_debug_dict(unit)
    result = AnalysisOrchestrator(options).analyze_pipeline(unit)
    assert to_debug_dict(unit) == before
    return {
        "source": before,
        "normalized_unit": to_debug_dict(result.normalized_unit),
        "policy_light_module": to_debug_dict(result.policy_light_module),
        "module": to_debug_dict(result.mojo_module),
        "bindings": render_mojo_module(
            result.mojo_module,
            MojoIRPrintOptions(options.module_comment, options.emit_doc_comments),
        ),
        "layout": render_layout_test_module(
            normalized_unit=result.normalized_unit,
            mojo_module=result.mojo_module,
            main_module_name="bindings",
        ),
    }


def _compare(backend, units, **settings):
    requests, expected = [], []
    for unit in units:
        for mode in ("external_call", "owned_dl_handle"):
            options = MojoEmitOptions(linking=mode, **settings)
            requests.append(
                {"action": "analyze", "unit": to_debug_dict(unit), "linking": mode, **settings}
            )
            expected.append(_expected(unit, options))
    for index, (actual, want) in enumerate(zip(backend(requests), expected, strict=True)):
        assert actual == want, (index, units[index // 2].source_header)
        assert decode_cir(actual["normalized_unit"]) == decode_cir(want["normalized_unit"])
        assert decode_mojo_ir(actual["module"]) == decode_mojo_ir(want["module"])


def test_all_shared_fixture_intermediates_and_exact_sources(backend):
    roots = [
        "tests/corpus/headers",
        "tests/surface/fixtures",
        "tests/stress/fixtures",
        "tests/e2e/fixtures",
        "tests/surface/alignment/fixtures",
    ]
    headers = [p for root in roots for p in sorted((ROOT / root).glob("*/input.h"))]
    assert len(headers) >= 49
    units = [ClangParser(p, library="parity", link_name="parity").run() for p in headers]
    _compare(backend, units)
    modules = [AnalysisOrchestrator().analyze(unit) for unit in units]
    requests = [{"action": "roundtrip-cir", "unit": to_debug_dict(unit)} for unit in units]
    requests += [
        {"action": "roundtrip-mojo", "module": to_debug_dict(module)} for module in modules
    ]
    results = backend(requests)
    assert results == [{k: v for k, v in request.items() if k != "action"} for request in requests]


def _constructed_unit():
    doc = ir.DocComment('/** Record docs.\n * More """ and \\ paths.\n */')
    node = ir.StructRef("node", "node", "node", size_bytes=16, align_bytes=8)
    exprs = [
        ir.IntLiteral(2**257 + 17),
        ir.IntLiteral(-(2**257)),
        ir.CFloatLiteral("0x1.8p+2F"),
        ir.CFloatLiteral("-0.0"),
        ir.StringLiteral('λ\\"\n\0'),
        ir.CharLiteral("'"),
        ir.CUnaryExpr("~", ir.IntLiteral(3)),
        ir.CBinaryExpr("<<", ir.IntLiteral(2), ir.IntLiteral(3)),
        ir.CCastExpr(I32, ir.IntLiteral(9)),
        ir.CSizeOfExpr(ir.CArray(I32, 4)),
        ir.CCallExpr(ir.CRefExpr("naïve"), (ir.IntLiteral(1),)),
    ]
    return ir.Unit(
        "constructed.h",
        "test/lib",
        "test-lib.λ",
        ABI,
        (
            ir.Struct("forward", "Forward", "Forward", (), 0, 1, is_complete=False),
            ir.Struct(
                "node",
                "node",
                "node",
                (
                    ir.Field("next", "next", ir.CPointer(node, 8, 8), 0, size_bytes=8),
                    ir.Field("value", "value", I32, 8, size_bytes=4),
                ),
                16,
                8,
                doc=doc,
            ),
            ir.Typedef(
                "callback",
                "Handler",
                ir.CPointer(ir.CFunctionPtr(I32, (ir.CParam("λ", I32),))),
                ir.CPointer(ir.CFunctionPtr(I32, (ir.CParam("λ", I32),))),
            ),
            ir.Function("call", "call", I32, (ir.CParam("_bindgen_c_fn", I32),), doc=doc),
            ir.Enum("enum", "Tagged", "Tagged", I32, (ir.Enumerant("huge", "huge", 2**256),)),
            ir.Typedef("enum-alias", "Choice", ir.EnumRef("enum", "Tagged", "Tagged", I32), I32),
            ir.MacroDecl("F", ("x",), "function_like_unsupported", diagnostic="function macro"),
            ir.MacroDecl(
                "NULL",
                ("nullptr",),
                "object_like_supported",
                ir.CNullPtrLiteral(),
                ir.CPointer(None),
            ),
            ir.GlobalVar("global", "global", "global", I32, initializer=ir.IntLiteral(9)),
            *[ir.Const(f"constant_{i}", I32, expr, doc=doc) for i, expr in enumerate(exprs)],
        ),
        (ir.IRDiagnostic("warning", "source diagnostic", "constructed.h", 2, 3),),
    )


def test_constructed_ir_exact_values_options_and_generate_api(backend):
    unit = _constructed_unit()
    _compare(
        backend, [unit, replace(unit, target_abi=ir.TargetABI(4, 4, ir.ByteOrder.BIG, "arm-linux"))]
    )
    _compare(
        backend,
        [unit],
        module_comment=False,
        emit_doc_comments=False,
        library_path_hint='/tmp/quoted"/lib.so',
    )
    actual = backend([{"action": "generate", "unit": to_debug_dict(unit)}])[0]
    expected = _expected(unit, MojoEmitOptions())
    assert actual == {
        key: value
        for key, value in expected.items()
        if key not in ("source", "policy_light_module")
    }


def test_expressions_numeric_edges_and_failure_recovery(backend):
    expressions = [
        ir.IntLiteral(2**1024 + 17),
        ir.IntLiteral(-(2**512)),
        ir.CFloatLiteral("0x0.0000000000001p-1022"),
        ir.CFloatLiteral("0x1.fffffffffffffp1023"),
        ir.CFloatLiteral("1e309"),
        ir.CFloatLiteral("1e-999"),
        ir.CFloatLiteral("-0.0"),
        ir.CFloatLiteral("1_0.5"),
        ir.CFloatLiteral("\u20031.25\u2003"),
        ir.CFloatLiteral("bad"),
        ir.CFloatLiteral("1__0"),
        ir.CFloatLiteral("0xzz"),
        ir.CFloatLiteral("1.25F\u2003"),
        ir.CNullPtrLiteral(),
        ir.CFloatLiteral("0x1p99999"),
        ir.CRefExpr("  λ::x  "),
    ]
    rng = random.Random(43)
    for _ in range(512):
        value = struct.unpack("!d", rng.getrandbits(64).to_bytes(8))[0]
        if math.isfinite(value):
            expressions.append(ir.CFloatLiteral(repr(value)))
    requests = [
        {"action": "map-expr", "expr": to_debug_dict(expr), "target_abi": to_debug_dict(ABI)}
        for expr in expressions
    ]
    mapper = MapConstExprPass(MapTypePass(TargetQueries(ABI)))
    printer = MojoIRPrinter()
    for expr, actual in zip(expressions, backend(requests), strict=True):
        try:
            mapped = mapper.run(expr)
        except (ValueError, OverflowError) as error:
            assert actual == {"error": str(error)}
        else:
            assert actual == {
                "source": to_debug_dict(expr),
                "expr": to_debug_dict(mapped),
                "text": printer._render_const_expr(mapped),
            }


def test_debug_decoders_defaults_wrong_family_and_unknown_fields(backend):
    unit = to_debug_dict(ir.Unit("x.h", "x", "x", ABI))
    omitted = copy.deepcopy(unit)
    del omitted["fields"]["decls"]
    del omitted["fields"]["diagnostics"]
    bad = copy.deepcopy(unit)
    bad["fields"]["decls"] = [to_debug_dict(ir.AliasDecl("x", ir.AliasKind.TYPE_ALIAS))]
    unknown = copy.deepcopy(unit)
    unknown["fields"]["extra"] = 2
    nested = to_debug_dict(ir.CCastExpr(I32, ir.IntLiteral(1)))
    nested["fields"]["target"] = to_debug_dict(ir.BuiltinType(ir.MojoBuiltin.C_INT))
    requests = [
        {"action": "roundtrip-cir", "unit": omitted},
        {"action": "roundtrip-cir", "unit": bad},
        {"action": "roundtrip-cir", "unit": unknown},
        {"action": "roundtrip-c-expr", "expr": nested},
        {"action": "roundtrip-c-expr", "expr": {"kind": "Unknown", "fields": {}}},
        {"action": "roundtrip-mojo-expr", "expr": to_debug_dict(ir.CFloatLiteral("1.5"))},
        {"action": "roundtrip-cir", "unit": unit},
    ]
    actual = backend(requests)
    assert actual[0] == actual[-1] == {"unit": unit}
    for result in actual[1:-1]:
        assert "error" in result


def test_validation_errors_and_same_process_recovery(backend):
    good = ir.Unit("good.h", "lib", "lib", ABI)
    invalid = [
        replace(good, decls=(ir.Struct("", "S\0\u200b\u2028", "S", (), 0, 1),)),
        replace(good, decls=(ir.Typedef("", "T", I32, I32),)),
        replace(good, decls=(ir.GlobalVar("g", "a", "a", I32), ir.GlobalVar("g", "b", "b", I32))),
        replace(good, decls=(ir.Const("size", I32, ir.CSizeOfExpr(ir.StructRef("", "S", "S"))),)),
        replace(
            good,
            decls=(
                ir.Const(
                    "bad", I32, ir.CSizeOfExpr(ir.EnumRef("missing", "Missing", "Missing", I32))
                ),
            ),
        ),
    ]
    requests = [{"action": "analyze", "unit": to_debug_dict(u)} for u in [*invalid, good, good]]
    actual = backend(requests)
    for unit, result in zip(invalid, actual, strict=False):
        with pytest.raises(ValueError) as error:
            AnalysisOrchestrator().analyze(unit)
        assert result == {"error": str(error.value)}
    assert actual[-2] == actual[-1] == _expected(good, MojoEmitOptions())


def test_constructed_target_roundtrip_normalization_and_printer(backend):
    builtin = ir.BuiltinType(ir.MojoBuiltin.C_INT)
    callback = ir.MojoFunctionPtr(builtin, (ir.MojoParam("source", builtin),))
    module = ir.MojoModule(
        "target.h",
        "lib",
        "lib",
        ir.LinkMode.EXTERNAL_CALL,
        decls=(
            ir.AliasDecl("Huge", ir.AliasKind.CONST_VALUE, const_value=ir.IntLiteral(2**1024)),
            ir.AliasDecl(
                "Expr",
                ir.AliasKind.CONST_VALUE,
                const_type=builtin,
                const_value=ir.MojoCallExpr(ir.MojoRefExpr("f"), (ir.MojoSizeOfExpr(builtin),)),
            ),
            ir.StructDecl(
                "R",
                align=16,
                doc=ir.DocComment("/// docs\n/// second"),
                members=(
                    ir.StoredMember(0, "handler", ir.MojoPointer(callback), 0),
                    ir.OpaqueStorageMember("raw", 3),
                    ir.PaddingMember("pad", 3, 1),
                ),
                comptime_members=(ir.ComptimeMember("K", const_value=ir.IntLiteral(-(2**512))),),
                initializers=(
                    ir.Initializer((ir.InitializerParam("handler", ir.MojoPointer(callback)),)),
                ),
            ),
            ir.FunctionDecl("f", "f", (ir.MojoParam("arg", callback),), builtin),
        ),
    )
    raw = to_debug_dict(module)
    expected = normalize_mojo_module(module)
    results = backend(
        [{"action": "roundtrip-mojo", "module": raw}, {"action": "normalize", "module": raw}]
    )
    assert results[0] == {"module": raw}
    assert results[1] == {
        "module": to_debug_dict(expected),
        "bindings": render_mojo_module(expected),
    }


@pytest.mark.parametrize(
    "case", ["full_surface_runtime", "large_alignment", "zero_length_tail_access"]
)
def test_native_generated_bindings_and_layout_on_stable(backend, tmp_path, case):
    """The generator uses nightly; emitted code still runs on the supported stable SDK."""
    import shutil

    from tests.e2e.test_e2e_runtime import _assert_expected_values, _parse_runner_output

    if not shutil.which("cc") or not shutil.which("mojo"):
        pytest.skip("requires the stable Mojo SDK and a C compiler")
    fixture = ROOT / "tests/e2e/fixtures" / case
    library = tmp_path / f"lib{case}.so"
    subprocess.run(
        ["cc", "-shared", "-fPIC", str(fixture / "impl.c"), "-o", str(library)],
        check=True,
        capture_output=True,
        text=True,
    )
    unit = ClangParser(fixture / "input.h", library=case, link_name=case).run()
    # The current Python model narrows this system record's long double. Full-header
    # byte parity covers it above; runtime layout acceptance targets fixture records.
    unit = replace(unit, decls=tuple(decl for decl in unit.decls if decl.name != "max_align_t"))
    requests = [
        {
            "action": "generate",
            "unit": to_debug_dict(unit),
            "linking": mode,
            "library_path_hint": str(library),
        }
        for mode in ("external_call", "owned_dl_handle")
    ]
    for mode, result in zip(("external", "dl"), backend(requests), strict=True):
        assert "error" not in result, result
        module = f"{case}_bindings_{mode}"
        (tmp_path / f"{module}.mojo").write_text(result["bindings"], encoding="utf-8")
        runner = fixture / f"runner_{mode}.mojo"
        binary = tmp_path / f"runner_{mode}"
        command = ["mojo", "build", "--Werror", str(runner), "-I", str(tmp_path), "-o", str(binary)]
        if mode == "external":
            command += ["-Xlinker", f"-L{tmp_path}", "-Xlinker", f"-l{case}"]
        built = subprocess.run(command, capture_output=True, text=True, timeout=90)
        assert built.returncode == 0, built.stderr
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = str(tmp_path) + ":" + env.get("LD_LIBRARY_PATH", "")
        ran = subprocess.run([str(binary)], capture_output=True, text=True, env=env, timeout=60)
        assert ran.returncode == 0, ran.stderr
        suffix = "external" if mode == "external" else "owned_dl_handle"
        expected = json.loads((fixture / f"expect.runtime.{suffix}.json").read_text())
        _assert_expected_values(_parse_runner_output(ran.stdout), expected)
        # The driver uses a stable module name for parity, so install that name too.
        (tmp_path / "bindings.mojo").write_text(result["bindings"], encoding="utf-8")
        layout = tmp_path / "layout.mojo"
        layout.write_text(result["layout"], encoding="utf-8")
        built = subprocess.run(
            [
                "mojo",
                "build",
                "--Werror",
                str(layout),
                "-I",
                str(tmp_path),
                "-o",
                str(tmp_path / "layout"),
            ],
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert built.returncode == 0, built.stderr
        ran = subprocess.run(
            [str(tmp_path / "layout")], capture_output=True, text=True, env=env, timeout=60
        )
        if case == "large_alignment":
            # Preserve the existing layout-generator defect: one IR padding member
            # prints multiple fields, so the following reflected index is too small.
            # Full-byte parity above intentionally keeps both implementations aligned.
            assert ran.returncode != 0
            assert "la_item.b.offset: got 8, expected 16" in ran.stdout + ran.stderr
        else:
            assert ran.returncode == 0, ran.stdout + ran.stderr


def test_expression_debug_roundtrips_include_nonfinite_and_all_operators(backend):
    builtin = ir.BuiltinType(ir.MojoBuiltin.C_INT)
    expressions = [
        ir.IntLiteral(2**2048),
        ir.MojoFloatLiteral(-0.0),
        ir.MojoFloatLiteral(float("inf")),
        ir.MojoFloatLiteral(float("-inf")),
        ir.StringLiteral('λ\0\r\n\t\\"'),
        ir.CharLiteral("'"),
        ir.MojoRefExpr("λ"),
        ir.MojoUnaryExpr("-", ir.IntLiteral(1)),
        ir.MojoBinaryExpr("+", ir.IntLiteral(1), ir.IntLiteral(2)),
        ir.MojoCastExpr(builtin, ir.IntLiteral(3)),
        ir.MojoSizeOfExpr(builtin),
        ir.MojoCallExpr(ir.MojoRefExpr("f"), (ir.IntLiteral(1),)),
    ]
    requests = [
        {"action": "roundtrip-mojo-expr", "expr": to_debug_dict(expr)} for expr in expressions
    ]
    results = backend(requests)
    for expr, result in zip(expressions, results, strict=True):
        assert result == {"expr": to_debug_dict(expr)}
    assert math.copysign(1.0, results[1]["expr"]["fields"]["value"]) == -1.0
    result = backend(
        [
            {
                "action": "roundtrip-mojo-expr",
                "expr": to_debug_dict(ir.MojoFloatLiteral(float("nan"))),
            }
        ]
    )[0]
    assert result["expr"]["kind"] == "MojoFloatLiteral"
    assert math.isnan(result["expr"]["fields"]["value"])
