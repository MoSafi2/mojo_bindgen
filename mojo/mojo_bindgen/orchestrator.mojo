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
    var analysis = AnalysisOrchestrator(emit_options.copy()).analyze_pipeline(unit)
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
