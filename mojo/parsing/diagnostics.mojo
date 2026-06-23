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

    def add_frontend_diagnostics(self, diags: List[FrontendDiagnostic]):
        """Append normalized frontend diagnostics from libclang."""
        for d in diags:
            self.diagnostics.append(d)

    def add_cursor_diag(
        self, severity: String, cursor: Cursor, message: String
    ) raises:
        """Append a cursor-based diagnostic."""
        var loc = cursor.location()
        var file_name = "<unknown>"
        var file_opt = loc.file()
        if file_opt:
            file_name = file_opt.value().name()
        self.diagnostics.append(FrontendDiagnostic(
            severity=severity,
            file=file_name,
            line=loc.line(),
            col=loc.column(),
            message=message,
        ))

    def add_type_diag(
        self, severity: String, clang_type: Type, message: String
    ) raises:
        """Append a type-based diagnostic when no source cursor is available."""
        self.diagnostics.append(FrontendDiagnostic(
            severity=severity,
            file="<type>",
            line=0,
            col=0,
            message=message + ": " + clang_type.spelling(),
        ))

    def to_ir_diagnostics(self) raises -> List[IRDiagnostic]:
        """Convert accumulated diagnostics into final IR diagnostics."""
        var out: List[IRDiagnostic] = []
        for d in self.diagnostics:
            out.append(IRDiagnostic(
                severity=d.severity,
                message=d.message,
                file=Optional[String](d.file),
                line=Optional[Int](d.line),
                col=Optional[Int](d.col),
                decl_id=None,
            ))
        return out^