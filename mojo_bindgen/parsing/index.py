"""Declaration indexing and identity services for one translation unit.

This module owns source-graph metadata for the parser package: stable
declaration identities, record definition lookups, top-level cursor ordering,
and anonymous record naming policy. It does not lower anything into IR.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import clang.cindex as cx

from mojo_bindgen.parsing.frontend import ClangFrontend


RECORD_KINDS = (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL)
NAMED_DECL_KINDS = (
    cx.CursorKind.STRUCT_DECL,
    cx.CursorKind.UNION_DECL,
    cx.CursorKind.ENUM_DECL,
    cx.CursorKind.TYPEDEF_DECL,
    cx.CursorKind.FUNCTION_DECL,
    cx.CursorKind.VAR_DECL,
)


def _location_key(cursor: cx.Cursor) -> str:
    loc = cursor.location
    return f"{loc.file}:{loc.line}:{loc.column}:{cursor.kind}:{cursor.spelling}"


def _is_anonymous_record_spelling(spelling: str) -> bool:
    return not spelling or "(unnamed at " in spelling or "(anonymous at " in spelling


def _sanitize_name_stem(raw: str, *, fallback: str) -> str:
    """Return a readable identifier-like stem for synthetic names."""
    text = raw.strip()
    if not text:
        return fallback
    text = re.sub(r"[^0-9A-Za-z_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    if not text:
        return fallback
    if text[0].isdigit():
        text = f"_{text}"
    return text


def _use_location_identity_for_cursor(cursor: cx.Cursor) -> bool:
    """Return whether ``cursor`` needs source-local identity instead of USR.

    libclang may report the same USR for sibling anonymous inline record
    definitions within one anonymous carrier. For anonymous struct/union
    declarations, use location-based identity so each definition remains
    distinct for lowering and caching.
    """
    return cursor.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL) and (
        _is_anonymous_record_spelling(cursor.spelling)
    )


@dataclass
class DeclIndex:
    """Identity and declaration index for one translation unit."""

    header: Path
    primary_cursors_in_order: tuple[cx.Cursor, ...]
    top_level_decl_ids: list[str]
    record_definition_by_decl_id: dict[str, cx.Cursor]
    anonymous_record_name_by_decl_id: dict[str, str]

    @classmethod
    def build_from_translation_unit(
        cls,
        tu: cx.TranslationUnit,
        frontend: ClangFrontend,
    ) -> DeclIndex:
        """Build a declaration index for primary-file cursors in one TU."""
        primary = tuple(frontend.iter_primary_cursors(tu))
        index = cls(
            header=frontend.header.resolve(),
            primary_cursors_in_order=primary,
            top_level_decl_ids=[],
            record_definition_by_decl_id={},
            anonymous_record_name_by_decl_id={},
        )

        for cursor in tu.cursor.walk_preorder():
            if not frontend.is_primary_file_cursor(cursor):
                continue
            if cursor.kind in RECORD_KINDS and cursor.is_definition():
                decl_id = index.decl_id_for_cursor(cursor)
                index.record_definition_by_decl_id[decl_id] = cursor

        index.top_level_decl_ids.extend(index.decl_id_for_cursor(cursor) for cursor in primary)

        return index

    def decl_id_for_cursor(self, cursor: cx.Cursor) -> str:
        """Return the stable declaration identity for a clang cursor."""
        usr = cursor.get_usr()
        if usr and not _use_location_identity_for_cursor(cursor):
            return usr

        if cursor.spelling and cursor.kind in NAMED_DECL_KINDS:
            return f"{cursor.kind.name}:{cursor.spelling}"

        loc_key = _location_key(cursor)
        digest = hashlib.sha256(loc_key.encode("utf-8")).hexdigest()[:16]
        return f"anon:{digest}"

    def record_definition_for_cursor(self, cursor: cx.Cursor) -> cx.Cursor | None:
        """Return the complete definition cursor for a record declaration."""
        decl_id = self.decl_id_for_cursor(cursor)
        return self.record_definition_by_decl_id.get(decl_id)

    def is_complete_record_decl(self, cursor: cx.Cursor) -> bool:
        """Return whether the record declaration has a complete definition."""
        if cursor.kind not in RECORD_KINDS:
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
        synth = self._anonymous_record_name(cursor, decl_id)
        return decl_id, synth, synth, True

    def _anonymous_record_name(self, cursor: cx.Cursor, decl_id: str) -> str:
        cached = self.anonymous_record_name_by_decl_id.get(decl_id)
        if cached is not None:
            return cached

        parent = self._naming_parent(cursor)
        parent_stem = self._scope_stem(parent) if parent is not None else ""
        kind = "anon_union" if cursor.kind == cx.CursorKind.UNION_DECL else "anon_struct"
        ordinal = self._anonymous_record_ordinal(cursor, parent)
        synth = f"{kind}_{ordinal}" if not parent_stem else f"{parent_stem}__{kind}_{ordinal}"
        self.anonymous_record_name_by_decl_id[decl_id] = synth
        return synth

    def _scope_stem(self, cursor: cx.Cursor | None) -> str:
        if cursor is None:
            return ""
        if cursor.kind == cx.CursorKind.FIELD_DECL:
            field_name = _sanitize_name_stem(cursor.spelling, fallback="field")
            parent = self._naming_parent(cursor)
            parent_stem = self._scope_stem(parent)
            return field_name if not parent_stem else f"{parent_stem}__{field_name}"
        if cursor.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            if _is_anonymous_record_spelling(cursor.spelling):
                return self._anonymous_record_name(cursor, self.decl_id_for_cursor(cursor))
            return _sanitize_name_stem(cursor.spelling, fallback="record")
        if cursor.spelling:
            return _sanitize_name_stem(cursor.spelling, fallback="scope")
        parent = self._naming_parent(cursor)
        return self._scope_stem(parent)

    def _naming_parent(self, cursor: cx.Cursor) -> cx.Cursor | None:
        parent = getattr(cursor, "lexical_parent", None) or getattr(cursor, "semantic_parent", None)
        if parent is None:
            return None
        if parent.kind == cx.CursorKind.TRANSLATION_UNIT:
            return None
        if not self.is_primary(parent):
            return None
        return parent

    def _anonymous_record_ordinal(self, cursor: cx.Cursor, parent: cx.Cursor | None) -> int:
        siblings = self.primary_cursors_in_order if parent is None else tuple(parent.get_children())
        target_loc = _location_key(cursor)
        ordinal = 0
        for sibling in siblings:
            if sibling.kind != cursor.kind:
                continue
            if not getattr(sibling, "is_definition", lambda: False)():
                continue
            if not _is_anonymous_record_spelling(sibling.spelling):
                continue
            ordinal += 1
            if _location_key(sibling) == target_loc:
                return ordinal
        return max(ordinal, 1)
