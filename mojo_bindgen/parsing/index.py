"""Declaration indexing and identity services for one translation unit.

This module owns source-graph metadata for the parser package: stable
declaration identities, record definition lookups, top-level cursor ordering,
and anonymous record naming policy. It does not lower anything into IR.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import clang.cindex as cx

from mojo_bindgen.parsing.frontend import ClangFrontend


def _location_key(cursor: cx.Cursor) -> str:
    loc = cursor.location
    return f"{loc.file}:{loc.line}:{loc.column}:{cursor.kind}:{cursor.spelling}"


def _is_anonymous_record_spelling(spelling: str) -> bool:
    return not spelling or "(unnamed at " in spelling or "(anonymous at " in spelling


@dataclass
class DeclIndex:
    """Identity and declaration index for one translation unit."""

    header: Path
    primary_cursors_in_order: tuple[cx.Cursor, ...]
    decl_id_by_usr: dict[str, str]
    decl_id_by_location: dict[str, str]
    cursor_by_decl_id: dict[str, cx.Cursor]
    top_level_decl_ids: list[str]
    record_definition_by_decl_id: dict[str, cx.Cursor]
    record_forward_decl_by_decl_id: dict[str, cx.Cursor]

    @classmethod
    def build_from_translation_unit(
        cls,
        tu: cx.TranslationUnit,
        frontend: ClangFrontend,
    ) -> DeclIndex:
        """Build a declaration index for primary-file cursors in one TU."""
        primary = tuple(frontend.iter_primary_cursors(tu))
        index = cls(
            header=frontend.header,
            primary_cursors_in_order=primary,
            decl_id_by_usr={},
            decl_id_by_location={},
            cursor_by_decl_id={},
            top_level_decl_ids=[],
            record_definition_by_decl_id={},
            record_forward_decl_by_decl_id={},
        )

        for cursor in tu.cursor.walk_preorder():
            if not frontend.is_primary_file_cursor(cursor):
                continue
            decl_id = index.decl_id_for_cursor(cursor)
            index.cursor_by_decl_id.setdefault(decl_id, cursor)
            if cursor.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
                if cursor.is_definition():
                    index.record_definition_by_decl_id[decl_id] = cursor
                else:
                    index.record_forward_decl_by_decl_id.setdefault(decl_id, cursor)

        for cursor in primary:
            decl_id = index.decl_id_for_cursor(cursor)
            index.top_level_decl_ids.append(decl_id)
            index.cursor_by_decl_id.setdefault(decl_id, cursor)

        return index

    def top_level_cursors(self) -> Iterable[cx.Cursor]:
        """Yield top-level primary-file cursors in source order."""
        return self.primary_cursors_in_order

    def decl_id_for_cursor(self, cursor: cx.Cursor) -> str:
        """Return the stable declaration identity for a clang cursor."""
        usr = cursor.get_usr()
        if usr:
            decl_id = self.decl_id_by_usr.get(usr)
            if decl_id is None:
                decl_id = usr
                self.decl_id_by_usr[usr] = decl_id
            return decl_id

        if cursor.spelling and cursor.kind in (
            cx.CursorKind.STRUCT_DECL,
            cx.CursorKind.UNION_DECL,
            cx.CursorKind.ENUM_DECL,
            cx.CursorKind.TYPEDEF_DECL,
            cx.CursorKind.FUNCTION_DECL,
            cx.CursorKind.VAR_DECL,
        ):
            stable = f"{cursor.kind.name}:{cursor.spelling}"
            self.decl_id_by_location.setdefault(stable, stable)
            return stable

        loc_key = _location_key(cursor)
        decl_id = self.decl_id_by_location.get(loc_key)
        if decl_id is None:
            digest = hashlib.sha256(loc_key.encode("utf-8")).hexdigest()[:16]
            decl_id = f"anon:{digest}"
            self.decl_id_by_location[loc_key] = decl_id
        return decl_id

    def record_definition_for_cursor(self, cursor: cx.Cursor) -> cx.Cursor | None:
        """Return the complete definition cursor for a record declaration."""
        decl_id = self.decl_id_for_cursor(cursor)
        return self.record_definition_by_decl_id.get(decl_id)

    def is_complete_record_decl(self, cursor: cx.Cursor) -> bool:
        """Return whether the record declaration has a complete definition."""
        if cursor.kind not in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            return False
        return self.record_definition_for_cursor(cursor) is not None

    def is_primary(self, cursor: cx.Cursor) -> bool:
        """Return whether a cursor originates from the configured header."""
        loc = cursor.location
        return bool(loc.file and Path(loc.file.name).resolve() == self.header)

    def record_identity(self, cursor: cx.Cursor) -> tuple[str, str, str, bool]:
        """Return stable identity fields for a lowered record declaration."""
        decl_id = self.decl_id_for_cursor(cursor)
        if not _is_anonymous_record_spelling(cursor.spelling):
            return decl_id, cursor.spelling, cursor.spelling, False
        suffix = decl_id.split(":", 1)[-1]
        synth = f"__bindgen_anon_{suffix}"
        return decl_id, synth, synth, True
