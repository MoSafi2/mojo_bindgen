"""Public parser facade and pipeline orchestration for C header parsing.

This module owns the parser package entrypoint. It validates user-facing input,
runs the staged parser pipeline, and returns the final Unit. Parsing policy
lives in dedicated frontend, registry, lowering, and diagnostics modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from clang import cindex as cx

from mojo_bindgen.analysis.pipeline import run_ir_passes
from mojo_bindgen.ir import Decl, Unit
from mojo_bindgen.parsing.diagnostics import ParserDiagnosticSink
from mojo_bindgen.parsing.frontend import (
    ClangCompat,
    ClangFrontend,
    ClangFrontendConfig,
    FrontendDiagnostic,
    _default_system_compile_args,
    _resolve_header_path,
)
from mojo_bindgen.parsing.lowering import (
    ConstExprParser,
    DeclLowerer,
    LiteralResolver,
    PrimitiveResolver,
    RecordLowerer,
    TypeLowerer,
)
from mojo_bindgen.parsing.registry import RecordRegistry


@dataclass(frozen=True)
class ParseSession:
    """Immutable per-run parser session shared across pipeline stages."""

    frontend: ClangFrontend
    tu: cx.TranslationUnit
    registry: RecordRegistry
    header: str
    library: str
    link_name: str


class ParseError(RuntimeError):
    """Raised when libclang reports fatal errors in the translation unit."""


class ClangParser:
    """Parse one C header and produce a `Unit`."""

    def __init__(
        self,
        header: Path | str,
        library: str,
        link_name: str,
        compile_args: list[str] | None = None,
        raise_on_error: bool = True,
    ) -> None:
        self.header = _resolve_header_path(header)
        self.library = library
        self.link_name = link_name
        self.compile_args = (
            _default_system_compile_args() if compile_args is None else list(compile_args)
        )
        self.raise_on_error = raise_on_error
        self.diagnostics: ParserDiagnosticSink = ParserDiagnosticSink()

    def run(self) -> Unit:
        """Parse the configured header into IR."""
        return run_ir_passes(self.run_raw())

    def run_raw(self) -> Unit:
        """Parse the configured header into raw source-faithful IR."""
        session = self._build_parser_session()
        self.session = session
        decl_lowerer = self._build_decl_lowerer(session)
        decls = self._collect_decls(session, decl_lowerer)
        return Unit(
            source_header=session.header,
            library=session.library,
            link_name=session.link_name,
            decls=decls,
            diagnostics=self.diagnostics.to_ir_diagnostics(),
        )

    def _build_parser_session(self) -> ParseSession:
        """Create frontend artifacts, collect diagnostics, and index declarations."""
        frontend = ClangFrontend(
            ClangFrontendConfig(
                header=self.header,
                compile_args=tuple(self.compile_args),
            )
        )
        tu = frontend.parse_translation_unit()
        frontend_diagnostics = frontend.collect_diagnostics(tu)
        self.diagnostics.add_frontend_diagnostics(frontend_diagnostics)
        _handle_frontend_errors(self.header, frontend_diagnostics, self.raise_on_error)

        registry = RecordRegistry.build_from_translation_unit(tu, frontend)
        return ParseSession(
            frontend=frontend,
            tu=tu,
            registry=registry,
            header=str(self.header),
            library=self.library,
            link_name=self.link_name,
        )

    def _build_decl_lowerer(self, session: ParseSession) -> DeclLowerer:
        """Build and wire lowering collaborators for this parsing session."""
        primitive_resolver = PrimitiveResolver()
        literal_resolver = LiteralResolver(self.compile_args)
        compat = ClangCompat()
        type_lowerer = TypeLowerer(
            registry=session.registry,
            diagnostics=self.diagnostics,
            primitive_resolver=primitive_resolver,
            compat=compat,
        )
        record_lowerer = RecordLowerer(
            registry=session.registry,
            diagnostics=self.diagnostics,
            type_lowerer=type_lowerer,
        )
        session.registry.bind_definition_lowerer(record_lowerer.lower_record_definition)
        return DeclLowerer(
            frontend=session.frontend,
            tu=session.tu,
            registry=session.registry,
            diagnostics=self.diagnostics,
            primitive_resolver=primitive_resolver,
            type_lowerer=type_lowerer,
            record_lowerer=record_lowerer,
            const_expr_parser=ConstExprParser(literal_resolver),
            compat=compat,
        )

    def _collect_decls(self, session: ParseSession, decl_lowerer: DeclLowerer) -> list[Decl]:
        """Lower top-level cursors and append macro declarations."""
        decls: list[Decl] = []
        completed_marker = 0
        for cursor in session.frontend.iter_primary_cursors(session.tu):
            lowered = decl_lowerer.lower_top_level_decl(cursor)
            if lowered is None:
                continue
            if isinstance(lowered, list):
                decls.extend(lowered)
                continue
            if cursor.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
                if cursor.is_definition() and cursor.spelling:
                    completed_marker, completed_records = (
                        decl_lowerer.record_lowerer.completed_records_since(completed_marker)
                    )
                    decls.extend(completed_records)
                else:
                    decls.append(lowered)
            else:
                decls.append(lowered)
        decls.extend(decl_lowerer.collect_macros())
        return decls


def _handle_frontend_errors(
    header: Path, frontend_diagnostics: list[FrontendDiagnostic], raise_on_error: bool
) -> None:
    fatal = [d for d in frontend_diagnostics if d.severity in ("error", "fatal")]
    if fatal and raise_on_error:
        message = "\n".join(str(d) for d in fatal)
        raise ParseError(f"libclang reported errors parsing {header}:\n{message}")


__all__ = [
    "ClangParser",
    "FrontendDiagnostic",
    "ParseError",
    "_default_system_compile_args",
    "_resolve_header_path",
]
