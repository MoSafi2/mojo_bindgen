"""Record lookup, naming, caching, and source-driven record materialization.

`RecordRegistry` is the record-scoped service layer that sits between the
parser frontend and the lowering pipeline. It indexes one
`clang.cindex.TranslationUnit` and provides:

- stable declaration IDs (`decl_id_for_cursor`)
- cached complete record definition cursors (`record_definition_for_decl`)
- stable naming policy for lowered record declarations (`record_naming`)
- cached lowered record definitions and `StructRef` creation
- anonymous definition materialization helpers for raw lowering

This module intentionally remains record-focused and source-driven. It does not
own post-parse normalization or semantic policy; those belong to IR passes.
Its only materialization step beyond direct lookup is lowering anonymous
complete record references that cannot be represented nominally without their
definition.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import clang.cindex as cx

from mojo_bindgen.ir import Struct, StructRef
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
    """Return a stable source-location key for a cursor."""
    loc = cursor.location
    return f"{loc.file}:{loc.line}:{loc.column}:{cursor.kind}:{cursor.spelling}"


def _is_anonymous_record_spelling(spelling: str) -> bool:
    """Heuristic for clang's synthetic spellings for anonymous records."""
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
    """Return whether ``cursor`` needs source-local identity instead of USR."""
    return cursor.kind in RECORD_KINDS and _is_anonymous_record_spelling(cursor.spelling)


@dataclass(frozen=True)
class RecordNaming:
    """Stable lowered naming metadata for one record declaration."""

    name: str
    c_name: str
    is_anonymous: bool


@dataclass
class RecordRegistry:
    """Record-scoped lookup, cache, and raw materialization service for one translation unit."""

    header: Path
    primary_cursors_in_order: tuple[cx.Cursor, ...]
    record_definition_by_decl_id: dict[str, cx.Cursor]
    anonymous_record_name_by_decl_id: dict[str, str]
    _records_by_decl_id: dict[str, Struct] = field(default_factory=dict)
    _completed_record_decl_ids: list[str] = field(default_factory=list)
    _definition_lowerer: Callable[[cx.Cursor], Struct] | None = None

    @classmethod
    def build_from_translation_unit(
        cls,
        tu: cx.TranslationUnit,
        frontend: ClangFrontend,
    ) -> RecordRegistry:
        """Index one translation unit for primary-file record declarations."""
        primary = tuple(frontend.iter_primary_cursors(tu))
        registry = cls(
            header=frontend.header.resolve(),
            primary_cursors_in_order=primary,
            record_definition_by_decl_id={},
            anonymous_record_name_by_decl_id={},
        )

        for cursor in tu.cursor.walk_preorder():
            if not frontend.is_primary_file_cursor(cursor):
                continue
            if cursor.kind in RECORD_KINDS and cursor.is_definition():
                decl_id = registry.decl_id_for_cursor(cursor)
                registry.record_definition_by_decl_id[decl_id] = cursor

        return registry

    def bind_definition_lowerer(
        self,
        lower_record_definition: Callable[[cx.Cursor], Struct],
    ) -> None:
        """Attach the record-definition lowerer used for anonymous materialization."""
        self._definition_lowerer = lower_record_definition

    def decl_id_for_cursor(self, cursor: cx.Cursor) -> str:
        """Return a stable declaration identity for a clang cursor."""
        usr = cursor.get_usr()
        if usr and not _use_location_identity_for_cursor(cursor):
            return usr

        if cursor.spelling and cursor.kind in NAMED_DECL_KINDS:
            return f"{cursor.kind.name}:{cursor.spelling}"

        loc_key = _location_key(cursor)
        digest = hashlib.sha256(loc_key.encode("utf-8")).hexdigest()[:16]
        return f"anon:{digest}"

    def record_definition_for_decl(self, cursor: cx.Cursor) -> cx.Cursor | None:
        """Return the complete clang definition cursor for a record declaration."""
        decl_id = self.decl_id_for_cursor(cursor)
        return self.record_definition_by_decl_id.get(decl_id)

    def is_complete_record_decl(self, cursor: cx.Cursor) -> bool:
        """Return whether a record cursor is backed by a complete definition."""
        if cursor.kind not in RECORD_KINDS:
            return False
        return self.record_definition_for_decl(cursor) is not None

    def is_primary(self, cursor: cx.Cursor) -> bool:
        """Return whether a cursor originates from the configured primary header."""
        loc = cursor.location
        return bool(loc.file and Path(loc.file.name).resolve() == self.header)

    def record_naming(self, cursor: cx.Cursor) -> RecordNaming:
        """Return stable lowered naming metadata for a record declaration."""
        decl_id = self.decl_id_for_cursor(cursor)
        if not _is_anonymous_record_spelling(cursor.spelling):
            return RecordNaming(
                name=cursor.spelling,
                c_name=cursor.spelling,
                is_anonymous=False,
            )
        synth = self._anonymous_record_name(cursor, decl_id)
        return RecordNaming(name=synth, c_name=synth, is_anonymous=True)

    def get(self, decl_id: str) -> Struct | None:
        """Return a cached lowered record definition when available."""
        return self._records_by_decl_id.get(decl_id)

    def store(self, struct: Struct) -> None:
        """Store a lowered record definition by declaration id."""
        self._records_by_decl_id[struct.decl_id] = struct

    def mark_completed(self, struct: Struct) -> None:
        """Record that one lowered record definition has finished field materialization."""
        if struct.decl_id not in self._completed_record_decl_ids:
            self._completed_record_decl_ids.append(struct.decl_id)

    def completed_records_since(self, start: int) -> tuple[int, list[Struct]]:
        """Return lowered record definitions completed after one marker index."""
        decl_ids = self._completed_record_decl_ids[start:]
        return len(self._completed_record_decl_ids), [
            self._records_by_decl_id[decl_id] for decl_id in decl_ids
        ]

    @staticmethod
    def make_struct_ref(struct: Struct) -> StructRef:
        """Build a stable StructRef from one lowered Struct."""
        return StructRef(
            decl_id=struct.decl_id,
            name=struct.name,
            c_name=struct.c_name,
            is_union=struct.is_union,
            size_bytes=struct.size_bytes,
            is_anonymous=struct.is_anonymous,
        )

    def materialize_record_definition(self, cursor: cx.Cursor) -> Struct:
        """Lower one complete record definition cursor and return the cached `Struct`."""
        decl_id = self.decl_id_for_cursor(cursor)
        cached = self.get(decl_id)
        if cached is not None:
            return cached
        return self._require_definition_lowerer()(cursor)

    def _require_definition_lowerer(
        self,
    ) -> Callable[[cx.Cursor], Struct]:
        if self._definition_lowerer is None:
            raise RuntimeError("RecordRegistry definition lowerer has not been bound")
        return self._definition_lowerer

    def _anonymous_record_name(self, cursor: cx.Cursor, decl_id: str) -> str:
        """Synthesize a stable IR-friendly name for an anonymous record."""
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
        """Compute the hierarchical “scope stem” part of an anonymous name."""
        if cursor is None:
            return ""
        if cursor.kind == cx.CursorKind.FIELD_DECL:
            field_name = _sanitize_name_stem(cursor.spelling, fallback="field")
            parent = self._naming_parent(cursor)
            parent_stem = self._scope_stem(parent)
            return field_name if not parent_stem else f"{parent_stem}__{field_name}"
        if cursor.kind in RECORD_KINDS:
            if _is_anonymous_record_spelling(cursor.spelling):
                return self._anonymous_record_name(cursor, self.decl_id_for_cursor(cursor))
            return _sanitize_name_stem(cursor.spelling, fallback="record")
        if cursor.spelling:
            return _sanitize_name_stem(cursor.spelling, fallback="scope")
        parent = self._naming_parent(cursor)
        return self._scope_stem(parent)

    def _naming_parent(self, cursor: cx.Cursor) -> cx.Cursor | None:
        """Choose the parent cursor used to derive an anonymous record scope stem."""
        parent = getattr(cursor, "lexical_parent", None) or getattr(cursor, "semantic_parent", None)
        if parent is None:
            return None
        if parent.kind == cx.CursorKind.TRANSLATION_UNIT:
            return None
        if not self.is_primary(parent):
            return None
        return parent

    def _anonymous_record_ordinal(self, cursor: cx.Cursor, parent: cx.Cursor | None) -> int:
        """Compute a stable ordinal among sibling anonymous record definitions."""
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
