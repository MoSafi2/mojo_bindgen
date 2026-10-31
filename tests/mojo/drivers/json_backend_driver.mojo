"""Continue real Python CLI debug dumps without a Python runtime in this process.

Usage: json-backend cir INPUT OUTPUT_DIR MODULE [LINK_MODE [LIBRARY_PATH]]
       json-backend mojo-ir INPUT OUTPUT_DIR MODULE
"""
from std.sys import argv
from mojo_bindgen.ir import LinkMode
from mojo_bindgen.serde import loads_cir, loads_mojo_ir, dumps_cir, dumps_mojo_ir
from mojo_bindgen import generate_from_unit, MojoEmitOptions, render_mojo_module


def _write(path: String, text: String) raises:
    with open(path, "w") as output:
        output.write(text)


def main() raises:
    var args = argv()
    if len(args) < 5 or len(args) > 7:
        raise Error("expected STAGE INPUT_JSON OUTPUT_DIR MODULE [LINK_MODE [LIBRARY_PATH]]")
    var text: String
    with open(args[2], "r") as source:
        text = source.read()
    var prefix = args[3] + "/" + args[4]
    if args[1] == "cir":
        var options = MojoEmitOptions()
        if len(args) >= 6:
            if args[5] == "owned_dl_handle":
                options.linking = LinkMode.OWNED_DL_HANDLE
            elif args[5] != "external_call":
                raise Error("expected external_call or owned_dl_handle")
        if len(args) == 7:
            options.library_path_hint = String(args[6])
        var result = generate_from_unit(loads_cir(text), options, String(args[4]))
        _write(prefix + ".mojo", result.bindings_source)
        _write(prefix + "_layout_tests.mojo", result.layout_test_source.value())
        _write(prefix + ".cir.json", dumps_cir(result.normalized_unit.ptr()[]))
        _write(prefix + ".mojo_ir.json", dumps_mojo_ir(result.mojo_module))
        print("CIR declarations: " + String(len(result.normalized_unit.ptr()[].decls)))
        print("MojoIR declarations: " + String(len(result.mojo_module.decls)))
    elif args[1] == "mojo-ir":
        if len(args) != 5:
            raise Error("MojoIR already contains linking options")
        var module = loads_mojo_ir(text)
        _write(prefix + ".mojo", render_mojo_module(module))
        _write(prefix + ".mojo_ir.json", dumps_mojo_ir(module))
        print("MojoIR declarations: " + String(len(module.decls)))
    else:
        raise Error("expected cir or mojo-ir")
