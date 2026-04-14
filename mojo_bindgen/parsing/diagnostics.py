"""Parser diagnostic collection and normalization.

This module owns parser-stage diagnostics after frontend parsing. Lowerers emit
warnings and errors through a shared sink instead of appending ad hoc mutable
lists. The sink is responsible for normalizing locations and converting parser
diagnostics into IR diagnostics for the final Unit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import clang.cindex as cx

from mojo_bindgen.ir import IRDiagnostic
from mojo_bindgen.parsing.frontend import FrontendDiagnostic


@dataclass
class ParserDiagnosticSink:
    """Collect frontend and lowering diagnostics for one parse run."""

    diagnostics: list[FrontendDiagnostic] = field(default_factory=list)

    def add_frontend_diagnostics(self, diagnostics: list[FrontendDiagnostic]) -> None:
        """Append normalized frontend diagnostics from libclang."""
        self.diagnostics.extend(diagnostics)

    def add_cursor_diag(self, severity: str, cursor: cx.Cursor, message: str) -> None:
        """Append a cursor-based diagnostic."""
        loc = cursor.location
        self.diagnostics.append(
            FrontendDiagnostic(
                severity=severity,
                file=loc.file.name if loc.file else "<unknown>",
                line=loc.line,
                col=loc.column,
                message=message,
            )
        )

    def add_type_diag(self, severity: str, clang_type: cx.Type, message: str) -> None:
        """Append a type-based diagnostic when no source cursor is available."""
        self.diagnostics.append(
            FrontendDiagnostic(
                severity=severity,
                file="<type>",
                line=0,
                col=0,
                message=f"{message}: {clang_type.spelling!r}",
            )
        )

    def to_ir_diagnostics(self) -> list[IRDiagnostic]:
        """Convert accumulated diagnostics into final IR diagnostics."""
        return [
            IRDiagnostic(
                severity=d.severity,
                message=d.message,
                file=d.file,
                line=d.line,
                col=d.col,
            )
            for d in self.diagnostics
        ]
