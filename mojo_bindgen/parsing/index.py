"""Declaration indexing and identity services for one translation unit.

`DeclIndex` is the small service layer that sits between the parser frontend
and the record/type lowering logic. It indexes a single
`clang.cindex.TranslationUnit` and provides:

- stable declaration IDs (`decl_id_for_cursor`)
- cached complete record definition cursors (`record_definition_for_decl`)
- stable record lowering identity + naming policy (`record_lowering_identity`)

This module intentionally does *not* lower anything into IR; it only owns
source-graph metadata and naming/identity decisions used by downstream
lowerers.
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
    """Return a stable source-location key for a cursor.

    Used for anonymous identity fallbacks and anonymous sibling ordinals.
    """
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
    """Identity and declaration index for one translation unit.

    Data model:
    - `primary_cursors_in_order`: primary-file cursors in deterministic preorder.
      This ordering is used to assign ordinals to anonymous record definitions
      so sibling anonymous records get distinct synthesized names.
    - `top_level_decl_ids`: `decl_id` values for each primary cursor. This is
      used to recognize “named top-level” decls during type resolution.
    - `record_definition_by_decl_id`: mapping from `decl_id` to the cached
      complete clang definition cursor for that record (struct/union only).
    - `anonymous_record_name_by_decl_id`: cache for synthesized IR-friendly
      names of anonymous record declarations.

    Identity rules (`decl_id_for_cursor`):
    - Prefer clang USR when present, except for anonymous inline record
      struct/union cursors where libclang may reuse the same USR for sibling
      definitions.
    - Otherwise, use a spelling-based fallback for “named decl kinds”.
    - Finally, fall back to a hashed location key with an `anon:` prefix.

    Anonymous naming rules (`record_lowering_identity`):
    - Anonymous record spellings trigger synthesized naming.
    - Synthesized names incorporate the anonymous record kind
      (`anon_struct`/`anon_union`), a stable ordinal, and a scope stem derived
      from lexical/semantic parents.
    """

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
        """Index one translation unit for primary-file declaration cursors.

        The index is limited to the frontend's configured primary/header file:
        we only record complete record definitions (`struct`/`union`) when the
        cursor originates from the primary file.
        """
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
        """Return a stable declaration identity for a clang cursor.

        This value is used as the cross-cursor key for caching record
        definitions and synthesized anonymous record names.

        Selection rules (three conditional “arms”):
        - USR arm: a normal named decl where clang provides a USR and the
          cursor is not an anonymous inline `struct`/`union` (for example
          `struct node { ... };`) => returns the USR.
        - `kind:spelling` arm: a named decl kind with an explicit spelling
          (for example `enum Color { ... }`) when USR is missing/unused =>
          returns `ENUM_DECL:Color` (or the appropriate `kind`).
        - `anon:` arm: an anonymous inline record whose spelling is empty or
          synthetic (for example `struct { int x; } inner;`) =>
          returns `anon:<hash>` derived from source location.
        """
        usr = cursor.get_usr()
        if usr and not _use_location_identity_for_cursor(cursor):
            return usr

        if cursor.spelling and cursor.kind in NAMED_DECL_KINDS:
            return f"{cursor.kind.name}:{cursor.spelling}"

        loc_key = _location_key(cursor)
        digest = hashlib.sha256(loc_key.encode("utf-8")).hexdigest()[:16]
        return f"anon:{digest}"

    def record_definition_for_decl(self, cursor: cx.Cursor) -> cx.Cursor | None:
        """Return the complete clang definition cursor for a record declaration.

        This resolves the incoming record declaration (forward or definition) to
        a stable `decl_id`, then returns the cached complete definition cursor
        for that `decl_id` if one exists (or `None` if the record is incomplete
        or was not indexed from the primary file).
        """
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

    def record_lowering_identity(self, cursor: cx.Cursor) -> tuple[str, str, str, bool]:
        """Return stable identity fields for lowering a record declaration.

        The returned tuple is:
        - `decl_id`: stable declaration identity (may be USR or an anonymous
          location-based fallback).
        - `name`: IR struct/union name (possibly synthesized for anonymous
          records).
        - `c_name`: C spelling name for diagnostics / mapping (currently the
          same as `name`).
        - `is_anonymous`: whether the cursor corresponds to an anonymous record
          that requires synthesized naming during lowering.

        Callers use the tuple to consistently populate `Struct` metadata and
        to decide how to treat nested anonymous record members.
        """
        decl_id = self.decl_id_for_cursor(cursor)
        if not _is_anonymous_record_spelling(cursor.spelling):
            return decl_id, cursor.spelling, cursor.spelling, False
        synth = self._anonymous_record_name(cursor, decl_id)
        return decl_id, synth, synth, True

    def _anonymous_record_name(self, cursor: cx.Cursor, decl_id: str) -> str:
        """Synthesize a stable IR-friendly name for an anonymous record.

        The name is derived from:
        - a scope stem based on the anonymous record's naming parent
        - the record kind (`anon_struct` / `anon_union`)
        - an ordinal derived from sibling anonymous record definitions

        Results are cached by `decl_id` because callers may see multiple
        cursors that map to the same declaration identity.
        """
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
        """Compute the hierarchical “scope stem” part of an anonymous name.

        For example, anonymous fields inside named structs get names that embed
        their field-name and parent scope chain.
        """
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
        """Choose the parent cursor used to derive an anonymous record scope stem.

        We prefer `lexical_parent` (falling back to `semantic_parent`) but only
        accept the parent when it originates from the configured primary header.
        """
        parent = getattr(cursor, "lexical_parent", None) or getattr(cursor, "semantic_parent", None)
        if parent is None:
            return None
        if parent.kind == cx.CursorKind.TRANSLATION_UNIT:
            return None
        if not self.is_primary(parent):
            return None
        return parent

    def _anonymous_record_ordinal(self, cursor: cx.Cursor, parent: cx.Cursor | None) -> int:
        """Compute a stable ordinal among sibling anonymous record definitions.

        Anonymous struct/union declarations may appear as siblings with equal
        USRs. To keep synthesized names distinct, we number them by their
        relative definition occurrence and stable source location.
        """
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
