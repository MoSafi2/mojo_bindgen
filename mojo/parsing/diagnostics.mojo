# Parser diagnostic collection and normalization.
#
# Ported from `mojo_bindgen/parsing/diagnostics.py`. Lowerers emit warnings and
# errors through a shared sink. The sink normalizes locations and converts
# parser diagnostics into IR diagnostics for the final Unit.

from clang.cindex import Cursor, Type
from mojo.parsing.frontend import FrontendDiagnostic
from mojo.ir import IRDiagnostic


struct ParserDiagnosticSink(Copyable, Movable):
    """Collect frontend and lowering diagnostics for one parse run."""

    var diagnostics: List[FrontendDiagnostic]

    def __init__(out self):
        self.diagnostics = List[FrontendDiagnostic]()

    def add_frontend_diagnostics(mut self, diags: List[FrontendDiagnostic]):
        """Append normalized frontend diagnostics from libclang."""
        for d in diags:
            self.diagnostics.append(d.copy())

    def add_cursor_diag(
        mut self, severity: String, cursor: Cursor, message: String
    ) raises:
        """Append a cursor-based diagnostic."""
        var loc = cursor.location()
        var file_name = "<unknown>"
        var file_opt = loc.file()
        if file_opt:
            file_name = file_opt.value().name()
        var diag = FrontendDiagnostic()
        diag.severity = severity
        diag.file = file_name
        diag.line = loc.line()
        diag.col = loc.column()
        diag.message = message
        self.diagnostics.append(diag^)

    def add_type_diag(
        mut self, severity: String, clang_type: Type, message: String
    ) raises:
        """Append a type-based diagnostic when no source cursor is available."""
        var diag = FrontendDiagnostic()
        diag.severity = severity
        diag.file = "<type>"
        diag.line = 0
        diag.col = 0
        diag.message = message + ": " + clang_type.spelling()
        self.diagnostics.append(diag^)

    def to_ir_diagnostics(self) raises -> List[IRDiagnostic]:
        """Convert accumulated diagnostics into final IR diagnostics."""
        var out: List[IRDiagnostic] = []
        for d in self.diagnostics:
            var diag = IRDiagnostic()
            diag.severity = d.severity
            diag.message = d.message
            diag.file = Optional[String](d.file)
            diag.line = Optional[Int](d.line)
            diag.col = Optional[Int](d.col)
            diag.decl_id = None
            out.append(diag^)
        return out^
