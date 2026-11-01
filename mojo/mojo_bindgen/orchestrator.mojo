"""Generation from constructed CIR; header parsing is a later native slice."""
from std.memory import ArcPointer
from .ir import Unit, MojoModule
from .analysis.pipeline import AnalysisOrchestrator
from .analysis.mojo.mojo_emit_options import MojoEmitOptions
from .codegen.mojo_ir_printer import render_mojo_module, MojoIRPrintOptions
from .layout_tests.generator import render_layout_test_module


@fieldwise_init
struct BackendResult(Copyable, Movable):
    var normalized_unit: ArcPointer[Unit]
    var mojo_module: MojoModule
    var bindings_source: String
    var layout_test_source: Optional[String]


def generate_from_unit(
    unit: Unit,
    emit_options: MojoEmitOptions = MojoEmitOptions(),
    layout_module_name: Optional[String] = {},
) raises -> BackendResult:
    var analysis = AnalysisOrchestrator(emit_options.copy()).analyze_normalized(unit)
    var source = render_mojo_module(
        analysis.mojo_module,
        MojoIRPrintOptions(emit_options.module_comment, emit_options.emit_doc_comments),
    )
    var layout = Optional[String]()
    if layout_module_name:
        layout = render_layout_test_module(
            analysis.normalized_unit.ptr()[], analysis.mojo_module, layout_module_name.value()
        )
    return BackendResult(
        analysis.normalized_unit.copy(), analysis.mojo_module.copy(), source^, layout^
    )


from .parsing.parser import ClangParser
from .parsing.frontend import (
    ClangOptions,
    ClangFrontend,
    default_system_compile_args,
    normalized_args,
)
from .parsing._process import command_output
from std.pathlib import Path


struct BindgenOptions(Copyable, Movable):
    var header: String
    var library: Optional[String]
    var link_name: Optional[String]
    var compile_args: Optional[List[String]]
    var clang_options: Optional[ClangOptions]
    var include_headers: List[String]
    var emit_options: MojoEmitOptions
    var layout_tests: Bool
    var output: Optional[String]
    var layout_test_output: Optional[String]
    var keep_going: Bool
    var clang_macro_fallback: Bool

    def __init__(out self, header: String):
        self.header = header.copy()
        self.library = None
        self.link_name = None
        self.compile_args = None
        self.clang_options = None
        self.include_headers = List[String]()
        self.emit_options = MojoEmitOptions()
        self.layout_tests = False
        self.output = None
        self.layout_test_output = None
        self.keep_going = False
        self.clang_macro_fallback = False


@fieldwise_init
struct BindgenResult(Copyable, Movable):
    var unit: Unit
    var mojo_module: MojoModule
    var bindings_source: String
    var layout_test_source: Optional[String]


def path_stem(path: String) -> String:
    var name = Path(path).name()
    var dot = name.rfind(".")
    if dot > 0:
        return String(name[byte=0:dot])
    return name^


struct BindgenOrchestrator(Copyable, Movable):
    var options: BindgenOptions

    def __init__(out self, var options: BindgenOptions):
        self.options = options^

    def normalized_clang_args(self) -> List[String]:
        var args: List[String]
        if self.options.clang_options:
            args = self.options.clang_options.value().to_args()
            args.extend(default_system_compile_args())
        elif self.options.compile_args:
            args = self.options.compile_args.value().copy()
        else:
            args = default_system_compile_args()
        if (
            self.options.emit_options.emit_doc_comments
            and "-fretain-comments-from-system-headers" not in args
        ):
            args.append("-fretain-comments-from-system-headers")
        return normalized_args(args)

    def parse(self) raises -> Unit:
        var library = self.options.library.value().copy() if self.options.library else path_stem(
            self.options.header
        )
        var link_name = (
            self.options.link_name.value().copy() if self.options.link_name else library.copy()
        )
        var parser = ClangParser(
            self.options.header,
            library,
            link_name,
            self.normalized_clang_args(),
            not self.options.keep_going,
            self.options.include_headers,
            self.options.clang_macro_fallback,
        )
        return parser.run()

    def dump_preprocessed(self) raises -> String:
        var frontend = ClangFrontend(
            self.options.header, self.normalized_clang_args(), self.options.include_headers
        )
        var args: List[String] = ["clang", "-E"]
        args.extend(frontend.compile_args.copy())
        if len(frontend.include_headers):
            args.append("-")
            return command_output(args, frontend.umbrella_source())
        args.append(frontend.header.copy())
        return command_output(args)

    def run(self) raises -> BindgenResult:
        var unit = self.parse()
        var module_name = Optional[String]()
        if self.options.layout_tests:
            module_name = path_stem(
                self.options.output.value() if self.options.output else self.options.header
            )
        var result = generate_from_unit(unit, self.options.emit_options, module_name)
        return BindgenResult(
            unit^,
            result.mojo_module.copy(),
            result.bindings_source.copy(),
            result.layout_test_source.copy(),
        )


def bindgen(options: BindgenOptions) raises -> BindgenResult:
    return BindgenOrchestrator(options.copy()).run()
