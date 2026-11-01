"""Native header CLI; debug JSON is optional output, never a runtime dependency."""
from std.pathlib import Path
from std.memory import ArcPointer
from std.ffi import external_call, c_int
from .orchestrator import BindgenOptions, BindgenOrchestrator
from .parsing.frontend import ClangOptions
from .ir import LinkMode, Unit
from .serde import dumps_cir, dumps_mojo_ir
from ._debug_json import JSON, dump_json
from ._numbers import IntegerValue
from ._installation import installation_root
from ._version import VERSION


def stderr(text: String):
    _ = external_call["write", Int](c_int(2), text.unsafe_ptr(), text.byte_length())


def help_text() -> String:
    return """Usage: mojo-bindgen [OPTIONS] HEADER

Generate Mojo FFI from C headers using libclang.

Input: --public-header PATH (repeat)
Clang: --clang-arg FLAG, -I/--include PATH, -D/--define NAME[=VALUE],
       -U/--undefine NAME, --std STD, --target TRIPLE, --sysroot PATH
Output: -o/--output PATH, --layout-tests PATH, --no-doc-comments
Linking: --library NAME, --link-name NAME,
         --link-mode external-call|owned-dl-handle, --library-path PATH
Diagnostics: --diagnostics text|json|silent, --diagnostics-output PATH,
             --warnings-as-errors
Other: --help, --version, --print-mojo-path
"""


def diagnostic_text(unit: Unit, mode: String) -> String:
    var result = String()
    var rows = List[ArcPointer[JSON]]()
    for d in unit.diagnostics:
        if mode == "json":
            var fields = Dict[String, ArcPointer[JSON]]()
            fields["stage"] = ArcPointer(JSON.string("frontend"))
            fields["severity"] = ArcPointer(JSON.string(d.severity.copy()))
            fields["message"] = ArcPointer(JSON.string(d.message.copy()))
            fields["file"] = ArcPointer(JSON.string(d.file.value()) if d.file else _null())
            fields["line"] = ArcPointer(
                JSON.integer(IntegerValue(d.line.value())) if d.line else _null()
            )
            fields["col"] = ArcPointer(
                JSON.integer(IntegerValue(d.col.value())) if d.col else _null()
            )
            fields["decl_id"] = ArcPointer(JSON.string(d.decl_id.value()) if d.decl_id else _null())
            rows.append(ArcPointer(JSON.object(fields^)))
        else:
            if result:
                result += "\n"
            result += (
                (d.file.value() if d.file else String("<unknown>"))
                + ":"
                + String(d.line.value() if d.line else 0)
                + ":"
                + String(d.col.value() if d.col else 0)
                + ": "
                + d.severity
                + ": "
                + d.message
            )
    if mode == "json":
        return dump_json(JSON.array(rows^))
    return result^


def run_cli(args: List[String]) -> Int:
    if len(args) == 1 or "--help" in args or "-h" in args:
        print(help_text(), end="")
        return 0
    if "--version" in args:
        print("mojo-bindgen " + String(VERSION))
        return 0
    if "--print-mojo-path" in args:
        print(installation_root() + "/mojo")
        return 0
    var options = BindgenOptions("")
    var clang = ClangOptions()
    var diagnostics = String("text")
    var diagnostics_output = Optional[String]()
    var cir = Optional[String]()
    var mojo_ir = Optional[String]()
    var preprocessed = Optional[String]()
    var warnings_as_errors = False
    var print_args = False
    var i = 1
    try:
        while i < len(args):
            var flag = args[i].copy()
            i += 1
            if flag == "--warnings-as-errors":
                warnings_as_errors = True
                continue
            if flag == "--no-doc-comments":
                options.emit_options.emit_doc_comments = False
                continue
            if flag == "--print-clang-args":
                print_args = True
                continue
            if not flag.startswith("-"):
                if options.header:
                    raise Error("unexpected positional argument: " + flag)
                options.header = flag^
                continue
            var value: String
            var eq = flag.find("=")
            if eq >= 0:
                value = String(flag[byte = eq + 1 :])
                var head = String(flag[byte=0:eq])
                flag = head^
            elif (
                flag.startswith("-I") or flag.startswith("-D") or flag.startswith("-U")
            ) and flag.byte_length() > 2:
                value = String(flag[byte=2:])
                var short_flag = String(flag[byte=0:2])
                flag = short_flag^
            else:
                if i == len(args):
                    raise Error("missing value for " + flag)
                value = args[i].copy()
                i += 1
            if flag == "--public-header":
                options.include_headers.append(value^)
            elif flag == "--clang-arg":
                clang.raw_args.append(value^)
            elif flag == "-I" or flag == "--include":
                clang.include_dirs.append(value^)
            elif flag == "-D" or flag == "--define":
                clang.defines.append(value^)
            elif flag == "-U" or flag == "--undefine":
                clang.undefines.append(value^)
            elif flag == "--std":
                clang.std = value^
            elif flag == "--target":
                clang.target = value^
            elif flag == "--sysroot":
                clang.sysroot = value^
            elif flag == "--library":
                options.library = value^
            elif flag == "--link-name":
                options.link_name = value^
            elif flag == "--library-path":
                options.emit_options.library_path_hint = value^
            elif flag == "--link-mode":
                var mode = value.lower()
                if mode == "owned-dl-handle":
                    options.emit_options.linking = LinkMode.OWNED_DL_HANDLE
                elif mode != "external-call":
                    raise Error("invalid link mode: " + value)
            elif flag == "-o" or flag == "--output":
                options.output = value^
            elif flag == "--layout-tests":
                options.layout_tests = True
                options.layout_test_output = value^
            elif flag == "--diagnostics":
                diagnostics = value.lower()
                if diagnostics != "text" and diagnostics != "json" and diagnostics != "silent":
                    raise Error("invalid diagnostic mode: " + value)
            elif flag == "--diagnostics-output":
                diagnostics_output = value^
            elif flag == "--dump-cir":
                cir = value^
            elif flag == "--dump-mojo-ir":
                mojo_ir = value^
            elif flag == "--dump-preprocessed":
                preprocessed = value^
            else:
                raise Error("unknown option: " + flag)
        if not options.header:
            raise Error("missing HEADER")
    except e:
        stderr("mojo-bindgen: " + String(e) + "\n")
        return 2
    options.clang_options = clang^
    try:
        var orchestrator = BindgenOrchestrator(options.copy())
        if print_args:
            var values = List[ArcPointer[JSON]]()
            for arg in orchestrator.normalized_clang_args():
                values.append(ArcPointer(JSON.string(arg.copy())))
            print(dump_json(JSON.array(values^)))
            return 0
        var preprocessed_text = Optional[String]()
        if preprocessed:
            preprocessed_text = orchestrator.dump_preprocessed()
        var result = orchestrator.run()
        # Complete the pipeline before publishing any binding or debug file.
        if preprocessed:
            Path(preprocessed.value()).write_text(preprocessed_text.value())
        if diagnostics != "silent" and len(result.unit.diagnostics):
            var text = diagnostic_text(result.unit, diagnostics) + "\n"
            if diagnostics_output:
                Path(diagnostics_output.value()).write_text(text)
            else:
                stderr(text)
        if cir:
            Path(cir.value()).write_text(dumps_cir(result.unit))
        if mojo_ir:
            Path(mojo_ir.value()).write_text(dumps_mojo_ir(result.mojo_module))
        if options.output:
            Path(options.output.value()).write_text(result.bindings_source)
        else:
            print(result.bindings_source, end="")
        if options.layout_test_output and result.layout_test_source:
            Path(options.layout_test_output.value()).write_text(result.layout_test_source.value())
        if warnings_as_errors:
            for d in result.unit.diagnostics:
                if d.severity == "warning":
                    return 1
        return 0
    except e:
        stderr("mojo-bindgen error: " + String(e) + "\nprimary header: " + options.header + "\n")
        return 1


def _null() -> JSON:
    return materialize[JSON.null]()
