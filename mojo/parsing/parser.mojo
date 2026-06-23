# Public parser facade for C header parsing.
#
# Ported from `mojo_bindgen/parsing/parser.py`. This module owns the parser
# package entrypoint. Full decl lowering is deferred to the lowering/ port;
# `run()` returns a Unit with empty decls but populated target_abi and
# diagnostics.

from clang.cindex import Cursor, CursorKind, TranslationUnit
from mojo.parsing.frontend import (
    ClangFrontend,
    ClangFrontendConfig,
    FrontendDiagnostic,
    _resolve_header_path,
    _default_system_compile_args,
    _parse_translation_unit_direct,
)
from mojo.parsing.diagnostics import ParserDiagnosticSink
from mojo.parsing.registry import RecordRegistry
from mojo.parsing.target_abi import probe_target_abi
from emberjson import Value
from mojo.ir import Unit, TargetABI
from std.pathlib import Path


@fieldwise_init
struct ParseSession(Copyable, Movable):
    """Immutable per-run parser session shared across pipeline stages."""

    var header: String
    var library: String
    var link_name: String
    # frontend, tu, registry are not stored here because TranslationUnit
    # is non-trivial. The ClangParser holds the session state directly.

    def __init__(out self):
        self.header = ""
        self.library = ""
        self.link_name = ""


def ParseError(message: String) -> Error:
    """Create a ParseError."""
    return Error("ParseError: " + message)


struct ClangParser(Copyable, Movable):
    """Parse one C header and produce a Unit.

    Phase-1 port: `run()` returns a Unit with empty decls but populated
    target_abi and diagnostics. Full decl lowering is deferred to the
    lowering/ port.
    """

    var header: String
    var include_headers: List[String]
    var library: String
    var link_name: String
    var compile_args: List[String]
    var raise_on_error: Bool
    var clang_macro_fallback: Bool
    var clang_macro_fallback_build_dir: Optional[String]
    var diagnostics: ParserDiagnosticSink

    def __init__(
        out self,
        header: String,
        library: String,
        link_name: String,
        compile_args: Optional[List[String]] = None,
        raise_on_error: Bool = True,
        include_headers: Optional[List[String]] = None,
        clang_macro_fallback: Bool = False,
        clang_macro_fallback_build_dir: Optional[String] = None,
    ) raises:
        self.header = _resolve_header_path(header)
        if include_headers:
            self.include_headers = _resolve_include_headers(
                self.header, include_headers.value()
            )
        else:
            self.include_headers = List[String]()
        self.library = library
        self.link_name = link_name
        if compile_args:
            self.compile_args = compile_args.value().copy()
        else:
            self.compile_args = _default_system_compile_args()
        self.raise_on_error = raise_on_error
        self.clang_macro_fallback = clang_macro_fallback
        self.clang_macro_fallback_build_dir = clang_macro_fallback_build_dir
        self.diagnostics = ParserDiagnosticSink()

    def run(mut self) raises -> Unit:
        """Parse the configured header into raw source-faithful IR.

        Phase-1: returns a Unit with empty decls but populated
        target_abi and diagnostics.
        """
        return self._parse_unit()

    def run_raw(mut self) raises -> Unit:
        """Compatibility alias for run()."""
        return self._parse_unit()

    def _parse_unit(mut self) raises -> Unit:
        """Parse the configured header into raw IR."""
        var session = self._build_parser_session()
        return Unit(
            "Unit",
            session.header,
            session.library,
            session.link_name,
            session.target_abi.copy(),
            List[Value](),
            self.diagnostics.to_ir_diagnostics(),
        )

    def _build_parser_session(mut self) raises -> _ParserSession:
        """Create frontend artifacts, collect diagnostics, and index declarations.
        """
        var frontend_config = ClangFrontendConfig()
        frontend_config.header = self.header
        frontend_config.compile_args = self.compile_args.copy()
        frontend_config.include_headers = self.include_headers.copy()
        var frontend = ClangFrontend(frontend_config^)

        var tu = frontend.parse_translation_unit()
        var frontend_diagnostics = frontend.collect_diagnostics(tu)
        self.diagnostics.add_frontend_diagnostics(frontend_diagnostics)
        _handle_frontend_errors(
            self.header, frontend_diagnostics, self.raise_on_error
        )

        var registry = RecordRegistry.build_from_translation_unit(tu, frontend)

        var target_abi = probe_target_abi(self.compile_args)

        return _ParserSession(
            self.header,
            self.library,
            self.link_name,
            target_abi.copy(),
        )


@fieldwise_init
struct _ParserSession(Copyable, Movable):
    """Internal parser session result."""

    var header: String
    var library: String
    var link_name: String
    var target_abi: TargetABI

    def __init__(out self):
        self.header = ""
        self.library = ""
        self.link_name = ""
        self.target_abi = TargetABI()


def _handle_frontend_errors(
    header: String,
    frontend_diagnostics: List[FrontendDiagnostic],
    raise_on_error: Bool,
) raises:
    """Raise ParseError if fatal diagnostics present and raise_on_error is True.
    """
    var has_fatal = False
    var messages: List[String] = []
    for d in frontend_diagnostics:
        if d.severity == "error" or d.severity == "fatal":
            has_fatal = True
            messages.append(String(d))
    if has_fatal and raise_on_error:
        var message = _join_strings(messages, "\n")
        raise ParseError(
            "libclang reported errors parsing " + header + ":\n" + message
        )


def _resolve_include_headers(
    primary_header: String,
    include_headers: List[String],
) raises -> List[String]:
    """Resolve, validate, and de-duplicate additional include headers."""
    var out: List[String] = []
    var seen: List[String] = [primary_header]
    for header in include_headers:
        var resolved = _resolve_header_path(header)
        var already_seen = False
        for s in seen:
            if s == resolved:
                already_seen = True
                break
        if already_seen:
            continue
        out.append(resolved)
        seen.append(resolved)
    return out^


def _join_strings(strings: List[String], separator: String) -> String:
    var result = ""
    var first = True
    for s in strings:
        if not first:
            result += separator
        result += s
        first = False
    return result
