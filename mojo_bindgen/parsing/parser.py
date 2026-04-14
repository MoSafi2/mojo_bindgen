"""Public parser facade and pipeline orchestration for C header parsing.

This module owns the parser package entrypoint. It validates user-facing input,
runs the staged parser pipeline, and returns the final Unit. Parsing policy
lives in dedicated frontend, indexing, lowering, and diagnostics modules.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

from mojo_bindgen.ir import Decl, Unit
from mojo_bindgen.parsing.compat import ClangCompat
from mojo_bindgen.parsing.diagnostics import ParserDiagnosticSink
from mojo_bindgen.parsing.frontend import (
    ClangFrontend,
    ClangFrontendConfig,
    FrontendDiagnostic,
    _default_system_compile_args,
    _resolve_header_path,
)
from mojo_bindgen.parsing.index import DeclIndex
from mojo_bindgen.parsing.lowering import (
    ConstExprParser,
    DeclLowerer,
    PrimitiveResolver,
    RecordLowerer,
    TypeLowerer,
)


@dataclass(frozen=True)
class ParseSession:
    """Immutable per-run parser session shared across pipeline stages."""

    frontend: ClangFrontend
    tu: object
    index: DeclIndex
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
            _default_system_compile_args()
            if compile_args is None
            else list(compile_args)
        )
        self.raise_on_error = raise_on_error
        self.diagnostics: list[FrontendDiagnostic] = []

    def run(self) -> Unit:
        """Parse the configured header into IR."""
        frontend = ClangFrontend(
            ClangFrontendConfig(
                header=self.header,
                compile_args=tuple(self.compile_args),
            )
        )
        tu = frontend.parse_translation_unit()
        frontend_diagnostics = frontend.collect_diagnostics(tu)
        self.diagnostics = frontend_diagnostics

        fatal = [d for d in self.diagnostics if d.severity in ("error", "fatal")]
        if fatal and self.raise_on_error:
            message = "\n".join(str(d) for d in fatal)
            raise ParseError(f"libclang reported errors parsing {self.header}:\n{message}")

        index = DeclIndex.build_from_translation_unit(tu, frontend)
        session = ParseSession(
            frontend=frontend,
            tu=tu,
            index=index,
            header=str(self.header),
            library=self.library,
            link_name=self.link_name,
        )
        diagnostics = ParserDiagnosticSink()
        diagnostics.add_frontend_diagnostics(frontend_diagnostics)
        primitive_resolver = PrimitiveResolver(self.compile_args)
        compat = ClangCompat()
        type_lowerer = TypeLowerer(
            index=session.index,
            diagnostics=diagnostics,
            primitive_resolver=primitive_resolver,
            compat=compat,
        )
        record_lowerer = RecordLowerer(
            index=session.index,
            diagnostics=diagnostics,
            type_lowerer=type_lowerer,
        )
        type_lowerer.bind_record_lowerer(record_lowerer)
        decl_lowerer = DeclLowerer(
            frontend=session.frontend,
            tu=session.tu,
            index=session.index,
            diagnostics=diagnostics,
            primitive_resolver=primitive_resolver,
            type_lowerer=type_lowerer,
            record_lowerer=record_lowerer,
            const_expr_parser=ConstExprParser(primitive_resolver),
            compat=compat,
        )

        decls: list[Decl] = []
        for cursor in session.index.top_level_cursors():
            lowered = decl_lowerer.lower_top_level_decl(cursor)
            if lowered is None:
                continue
            if isinstance(lowered, list):
                decls.extend(lowered)
            else:
                decls.append(lowered)

        decls.extend(decl_lowerer.collect_macros())

        self.diagnostics = diagnostics.diagnostics
        return Unit(
            source_header=session.header,
            library=session.library,
            link_name=session.link_name,
            decls=decls,
            diagnostics=diagnostics.to_ir_diagnostics(),
        )


__all__ = [
    "ClangParser",
    "FrontendDiagnostic",
    "ParseError",
    "_default_system_compile_args",
    "_resolve_header_path",
]
