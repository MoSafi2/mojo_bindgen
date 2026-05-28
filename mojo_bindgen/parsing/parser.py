"""Public parser facade for C header parsing.

This module owns the parser package entrypoint. It validates user-facing input,
runs the staged parser pipeline, and returns the final Unit. Parsing policy
lives in dedicated frontend, registry, lowering, and diagnostics modules.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from clang import cindex as cx

from mojo_bindgen.analysis.type_walk import TypeWalkOptions, collect_type_nodes
from mojo_bindgen.ir import Decl, Struct, StructRef, TargetABI, Type, Unit
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
from mojo_bindgen.parsing.target_abi import probe_target_abi


@dataclass(frozen=True)
class ParseSession:
    """Immutable per-run parser session shared across pipeline stages."""

    frontend: ClangFrontend
    tu: cx.TranslationUnit
    registry: RecordRegistry
    header: str
    library: str
    link_name: str
    target_abi: TargetABI


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
        include_headers: Sequence[Path | str] | None = None,
    ) -> None:
        self.header = _resolve_header_path(header)
        self.include_headers = _resolve_include_headers(self.header, include_headers)
        self.library = library
        self.link_name = link_name
        self.compile_args = (
            _default_system_compile_args() if compile_args is None else list(compile_args)
        )
        self.raise_on_error = raise_on_error
        self.diagnostics: ParserDiagnosticSink = ParserDiagnosticSink()

    def run(self) -> Unit:
        """Parse the configured header into raw source-faithful CIR."""
        return self._parse_unit()

    def run_raw(self) -> Unit:
        """Compatibility alias for :meth:`run`."""
        return self._parse_unit()

    def _parse_unit(self) -> Unit:
        """Parse the configured header into raw source-faithful IR."""
        session = self._build_parser_session()
        self.session = session
        decl_lowerer = self._build_decl_lowerer(session)
        decls = self._collect_decls(session, decl_lowerer)
        return Unit(
            source_header=session.header,
            library=session.library,
            link_name=session.link_name,
            target_abi=session.target_abi,
            decls=decls,
            diagnostics=self.diagnostics.to_ir_diagnostics(),
        )

    def _build_parser_session(self) -> ParseSession:
        """Create frontend artifacts, collect diagnostics, and index declarations."""
        frontend = ClangFrontend(
            ClangFrontendConfig(
                header=self.header,
                compile_args=tuple(self.compile_args),
                include_headers=tuple(self.include_headers),
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
            target_abi=probe_target_abi(self.compile_args),
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
        for cursor in session.frontend.iter_emittable_cursors(session.tu):
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
        completed_marker, materialized_records = self._materialize_embedded_record_decls(
            session,
            decls,
            decl_lowerer,
            completed_marker,
        )
        decls.extend(materialized_records)

        return decls

    def _materialize_embedded_record_decls(
        self,
        session: ParseSession,
        decls: list[Decl],
        decl_lowerer: DeclLowerer,
        completed_marker: int,
    ) -> tuple[int, list[Struct]]:
        """Materialize complete named record definitions required by embedded-by-value fields."""

        emitted_decl_ids = {decl.decl_id for decl in decls if isinstance(decl, Struct)}
        materialized: list[Struct] = []
        cursor_by_decl_id = session.registry.record_definition_by_decl_id

        while True:
            needed_decl_ids: list[str] = []
            for decl in [decl for decl in decls if isinstance(decl, Struct)] + materialized:
                for ref in _embedded_struct_refs_for_struct(decl):
                    if ref.decl_id in emitted_decl_ids:
                        continue
                    if ref.decl_id not in cursor_by_decl_id:
                        continue
                    if ref.decl_id in needed_decl_ids:
                        continue
                    needed_decl_ids.append(ref.decl_id)

            if not needed_decl_ids:
                break

            for decl_id in needed_decl_ids:
                session.registry.materialize_record_definition(cursor_by_decl_id[decl_id])

            new_marker, new_records = decl_lowerer.record_lowerer.completed_records_since(
                completed_marker
            )
            completed_marker = new_marker
            fresh_records = [
                record
                for record in new_records
                if record is not None and record.decl_id not in emitted_decl_ids
            ]
            if not fresh_records:
                break
            materialized.extend(fresh_records)
            emitted_decl_ids.update(record.decl_id for record in fresh_records)

        return completed_marker, materialized


def _embedded_struct_refs_for_struct(decl: Struct) -> tuple[StructRef, ...]:
    refs: list[StructRef] = []
    for field in decl.fields:
        refs.extend(_embedded_struct_refs(field.type))
    return tuple(refs)


def _embedded_struct_refs(t: Type) -> tuple[StructRef, ...]:
    out = [
        node
        for node in collect_type_nodes(
            t,
            lambda node: isinstance(node, StructRef) and not node.is_union,
            options=TypeWalkOptions(
                descend_pointer=False,
                descend_function_ptr=False,
                descend_vector_element=True,
            ),
        )
        if isinstance(node, StructRef)
    ]
    return tuple(out)


def _handle_frontend_errors(
    header: Path, frontend_diagnostics: list[FrontendDiagnostic], raise_on_error: bool
) -> None:
    fatal = [d for d in frontend_diagnostics if d.severity in ("error", "fatal")]
    if fatal and raise_on_error:
        message = "\n".join(str(d) for d in fatal)
        raise ParseError(f"libclang reported errors parsing {header}:\n{message}")


def _resolve_include_headers(
    primary_header: Path,
    include_headers: Sequence[Path | str] | None,
) -> list[Path]:
    """Resolve, validate, and de-duplicate additional include headers."""
    if include_headers is None:
        return []
    out: list[Path] = []
    seen: set[Path] = {primary_header.resolve()}
    for header in include_headers:
        resolved = _resolve_header_path(header)
        if resolved in seen:
            continue
        out.append(resolved)
        seen.add(resolved)
    return out


__all__ = [
    "ClangParser",
    "FrontendDiagnostic",
    "ParseError",
    "_default_system_compile_args",
    "_resolve_header_path",
    "_resolve_include_headers",
]
