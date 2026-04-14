"""Translation-unit declaration registry and identity services."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import clang.cindex as cx

from mojo_bindgen.parsing.frontend import ClangFrontend


def _location_key(cursor: cx.Cursor) -> str:
    loc = cursor.location
    return f"{loc.file}:{loc.line}:{loc.column}:{cursor.kind}:{cursor.spelling}"


def _is_anonymous_record_spelling(spelling: str) -> bool:
    return not spelling or "(unnamed at " in spelling


@dataclass
class DeclRegistry:
    """Identity and declaration index for one translation unit."""

    header: Path
    decl_id_by_usr: dict[str, str]
    decl_id_by_location: dict[str, str]
    cursor_by_decl_id: dict[str, cx.Cursor]
    top_level_decl_ids: list[str]
    primary_decl_ids_in_order: list[str]
    record_definition_by_decl_id: dict[str, cx.Cursor]
    record_forward_decl_by_decl_id: dict[str, cx.Cursor]

    @classmethod
    def build_from_translation_unit(
        cls,
        tu: cx.TranslationUnit,
        frontend: ClangFrontend,
    ) -> DeclRegistry:
        registry = cls(
            header=frontend.header,
            decl_id_by_usr={},
            decl_id_by_location={},
            cursor_by_decl_id={},
            top_level_decl_ids=[],
            primary_decl_ids_in_order=[],
            record_definition_by_decl_id={},
            record_forward_decl_by_decl_id={},
        )

        for cursor in tu.cursor.walk_preorder():
            if not frontend.is_primary_file_cursor(cursor):
                continue
            decl_id = registry.decl_id_for_cursor(cursor)
            registry.cursor_by_decl_id.setdefault(decl_id, cursor)
            if cursor.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
                if cursor.is_definition():
                    registry.record_definition_by_decl_id[decl_id] = cursor
                else:
                    registry.record_forward_decl_by_decl_id.setdefault(decl_id, cursor)

        for cursor in frontend.iter_primary_cursors(tu):
            decl_id = registry.decl_id_for_cursor(cursor)
            registry.top_level_decl_ids.append(decl_id)
            registry.primary_decl_ids_in_order.append(decl_id)
            registry.cursor_by_decl_id.setdefault(decl_id, cursor)

        return registry

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

    def decl_id_for_type_record(self, t: cx.Type) -> str | None:
        """Return the record declaration id for a clang record type."""
        decl = t.get_declaration()
        if decl.kind not in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            return None
        return self.decl_id_for_cursor(decl)

    def cursor_for_decl_id(self, decl_id: str) -> cx.Cursor | None:
        """Return the indexed cursor for a declaration id, if any."""
        return self.cursor_by_decl_id.get(decl_id)

    def record_definition_for_cursor(self, cursor: cx.Cursor) -> cx.Cursor | None:
        """Return the complete definition cursor for a record declaration."""
        decl_id = self.decl_id_for_cursor(cursor)
        return self.record_definition_by_decl_id.get(decl_id)

    def record_definition_for_type(self, t: cx.Type) -> cx.Cursor | None:
        """Return the complete definition cursor for a record type."""
        decl_id = self.decl_id_for_type_record(t)
        if decl_id is None:
            return None
        return self.record_definition_by_decl_id.get(decl_id)

    def is_complete_record_decl(self, cursor: cx.Cursor) -> bool:
        """Return whether the record declaration has a complete definition."""
        if cursor.kind not in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            return False
        return self.record_definition_for_cursor(cursor) is not None

    def is_primary_file_cursor(self, cursor: cx.Cursor) -> bool:
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
