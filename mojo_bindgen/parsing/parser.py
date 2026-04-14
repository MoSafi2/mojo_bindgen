"""Public parser facade for C header to IR translation."""

from __future__ import annotations

from pathlib import Path

from mojo_bindgen.ir import Decl, Unit
from mojo_bindgen.parsing.frontend import (
    ClangFrontend,
    ClangFrontendConfig,
    FrontendDiagnostic,
    _default_system_compile_args,
    _resolve_header_path,
)
from mojo_bindgen.parsing.lowering import DeclLowerer, LoweringContext, PrimitiveResolver
from mojo_bindgen.parsing.registry import DeclRegistry


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
        self.diagnostics = frontend.collect_diagnostics(tu)

        fatal = [d for d in self.diagnostics if d.severity in ("error", "fatal")]
        if fatal and self.raise_on_error:
            message = "\n".join(str(d) for d in fatal)
            raise ParseError(f"libclang reported errors parsing {self.header}:\n{message}")

        registry = DeclRegistry.build_from_translation_unit(tu, frontend)
        context = LoweringContext(
            frontend=frontend,
            registry=registry,
            tu=tu,
            header=str(self.header),
            library=self.library,
            link_name=self.link_name,
            diagnostics=list(self.diagnostics),
            primitive_resolver=PrimitiveResolver(self.compile_args),
        )

        decls: list[Decl] = []
        decl_lowerer: DeclLowerer = context.decl_lowerer
        for cursor in frontend.iter_primary_cursors(tu):
            lowered = decl_lowerer.lower_top_level_decl(cursor)
            if lowered is None:
                continue
            if isinstance(lowered, list):
                decls.extend(lowered)
            else:
                decls.append(lowered)

        decls.extend(decl_lowerer.collect_macros())

        self.diagnostics = context.diagnostics
        return Unit(
            source_header=str(self.header),
            library=self.library,
            link_name=self.link_name,
            decls=decls,
            diagnostics=context.to_ir_diagnostics(),
        )


__all__ = [
    "ClangParser",
    "FrontendDiagnostic",
    "ParseError",
    "_default_system_compile_args",
    "_resolve_header_path",
]
