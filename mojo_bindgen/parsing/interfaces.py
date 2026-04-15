"""Internal parser interfaces and narrow collaboration contracts.

This module defines capability-oriented interfaces between parser stages so
implementation modules can depend on small roles rather than a shared mutable
context object. These are internal contracts for the parser package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import clang.cindex as cx

from mojo_bindgen.ir import IRDiagnostic, Primitive, Struct, StructRef, Type


class DeclarationIndex(Protocol):
    """Index source declarations and answer identity/definition lookups."""

    header: Path
    top_level_decl_ids: list[str]

    def decl_id_for_cursor(self, cursor: cx.Cursor) -> str: ...

    def record_definition_for_cursor(self, cursor: cx.Cursor) -> cx.Cursor | None: ...

    def is_complete_record_decl(self, cursor: cx.Cursor) -> bool: ...

    def record_identity(self, cursor: cx.Cursor) -> tuple[str, str, str, bool]: ...

    def is_primary(self, cursor: cx.Cursor) -> bool: ...


class DiagnosticSink(Protocol):
    """Collect parser diagnostics and expose IR-normalized diagnostics."""

    def add_cursor_diag(self, severity: str, cursor: cx.Cursor, message: str) -> None: ...

    def add_type_diag(self, severity: str, clang_type: cx.Type, message: str) -> None: ...

    def to_ir_diagnostics(self) -> list[IRDiagnostic]: ...


class LiteralPrimitiveResolver(Protocol):
    """Resolve primitive types for parsed literals."""

    def primitive_for_integer_literal_suffix(self, suffix: str) -> Primitive: ...


class TypeLowering(Protocol):
    """Lower one clang type into one IR type."""

    def lower(self, clang_type: cx.Type, ctx: object) -> Type: ...


class RecordLowering(Protocol):
    """Lower record declarations and build stable struct references."""

    def lower_top_level_record(self, cursor: cx.Cursor) -> list[Struct] | Struct | None: ...

    def lower_record_definition(self, cursor: cx.Cursor) -> tuple[list[Struct], Struct]: ...

    def make_struct_ref(self, struct: Struct) -> StructRef: ...


class RecordTypeResolving(Protocol):
    """Resolve clang record types through a record-focused collaboration point."""

    def lower_record_type(self, clang_type: cx.Type) -> Type: ...
