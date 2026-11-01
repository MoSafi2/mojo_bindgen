"""Test-only JSON boundary: constructed CIR enters an independent native backend."""
from std.memory import ArcPointer
from std.sys import argv
from mojo_bindgen.ir import *
from mojo_bindgen.serde import *
from mojo_bindgen._debug_json import JSON, dump_json, parse_json
from mojo_bindgen.analysis.pipeline import AnalysisOrchestrator
from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.mojo.const_expr_mapping import MapConstExprPass
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.cir.cir_canonicalizer import CIRCanonicalizer
from mojo_bindgen.codegen.normalize_mojo_module import normalize_mojo_module
from mojo_bindgen.codegen.mojo_ir_printer import (
    render_mojo_module,
    render_const_expr,
    MojoIRPrintOptions,
)
from mojo_bindgen.layout_tests.generator import render_layout_test_module
from mojo_bindgen.orchestrator import generate_from_unit
from mojo_bindgen.parsing.lowering.const_expr import fold


def _options(req: JSON) raises -> MojoEmitOptions:
    var options = MojoEmitOptions()
    if req.has("linking") and req.get("linking").ptr()[].text() == "owned_dl_handle":
        options.linking = LinkMode.OWNED_DL_HANDLE
    if req.has("library_path_hint"):
        options.library_path_hint = req.get("library_path_hint").ptr()[].text()
    if req.has("module_comment"):
        options.module_comment = req.get("module_comment").ptr()[].bool_value()
    if req.has("emit_doc_comments"):
        options.emit_doc_comments = req.get("emit_doc_comments").ptr()[].bool_value()
    return options^


def _run(req: JSON) raises -> JSON:
    var response = Dict[String, ArcPointer[JSON]]()
    var action = req.get("action").ptr()[].text()
    if action == "fold":
        response["expr"] = ArcPointer(encode_c_expr(fold(decode_c_expr(req.get("expr").ptr()[]))))
    elif action == "roundtrip-cir":
        response["unit"] = ArcPointer(encode_cir(decode_cir(req.get("unit").ptr()[])))
    elif action == "roundtrip-mojo":
        response["module"] = ArcPointer(encode_mojo_ir(decode_mojo_ir(req.get("module").ptr()[])))
    elif action == "roundtrip-c-expr":
        response["expr"] = ArcPointer(encode_c_expr(decode_c_expr(req.get("expr").ptr()[])))
    elif action == "roundtrip-mojo-expr":
        response["expr"] = ArcPointer(encode_mojo_expr(decode_mojo_expr(req.get("expr").ptr()[])))
    elif action == "map-expr":
        var expr = decode_c_expr(req.get("expr").ptr()[])
        var mapper = MapConstExprPass(
            MapTypePass(TargetQueries(decode_target_abi(req.get("target_abi").ptr()[])))
        )
        var mapped = mapper.run(expr)
        response["source"] = ArcPointer(encode_c_expr(expr))
        response["expr"] = ArcPointer(encode_mojo_expr(mapped))
        response["text"] = ArcPointer(JSON.string(render_const_expr(mapped)))
    elif action == "canonicalize":
        response["unit"] = ArcPointer(
            encode_cir(CIRCanonicalizer().canonicalize(decode_cir(req.get("unit").ptr()[])))
        )
    elif action == "normalize" or action == "render":
        var module = decode_mojo_ir(req.get("module").ptr()[])
        if action == "normalize":
            module = normalize_mojo_module(module)
        response["module"] = ArcPointer(encode_mojo_ir(module))
        var options = _options(req)
        response["bindings"] = ArcPointer(
            JSON.string(
                render_mojo_module(
                    module, MojoIRPrintOptions(options.module_comment, options.emit_doc_comments)
                )
            )
        )
    elif action == "generate":
        var result = generate_from_unit(
            decode_cir(req.get("unit").ptr()[]), _options(req), String("bindings")
        )
        response["normalized_unit"] = ArcPointer(encode_cir(result.normalized_unit.ptr()[]))
        response["module"] = ArcPointer(encode_mojo_ir(result.mojo_module))
        response["bindings"] = ArcPointer(JSON.string(result.bindings_source))
        response["layout"] = ArcPointer(JSON.string(result.layout_test_source.value()))
    elif action == "analyze":
        var unit = decode_cir(req.get("unit").ptr()[])
        var options = _options(req)
        var analysis = AnalysisOrchestrator(options.copy()).analyze_pipeline(unit)
        response["source"] = ArcPointer(encode_cir(unit))
        response["normalized_unit"] = ArcPointer(encode_cir(analysis.normalized_unit.ptr()[]))
        response["policy_light_module"] = ArcPointer(encode_mojo_ir(analysis.policy_light_module))
        response["module"] = ArcPointer(encode_mojo_ir(analysis.mojo_module))
        response["bindings"] = ArcPointer(
            JSON.string(
                render_mojo_module(
                    analysis.mojo_module,
                    MojoIRPrintOptions(options.module_comment, options.emit_doc_comments),
                )
            )
        )
        response["layout"] = ArcPointer(
            JSON.string(
                render_layout_test_module(
                    analysis.normalized_unit.ptr()[], analysis.mojo_module, "bindings"
                )
            )
        )
    else:
        raise Error("unknown backend test action: " + action)
    return JSON.object(response^)


def main() raises:
    var args = argv()
    var text: String
    with open(args[1], "r") as f:
        text = f.read()
    var requests = parse_json(text)
    for req in requests.items():
        try:
            print(dump_json(_run(req.ptr()[])))
        except error:
            var response = Dict[String, ArcPointer[JSON]]()
            response["error"] = ArcPointer(JSON.string(String(error)))
            print(dump_json(JSON.object(response^)))
