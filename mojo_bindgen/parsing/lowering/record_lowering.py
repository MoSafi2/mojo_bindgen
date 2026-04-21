"""Struct and union lowering for raw parser IR construction.

This module owns source-driven record lowering and normalized field-site
discovery for inline record definitions. It may delegate type conversion to the
type lowerer, but it does not own post-parse normalization or semantic policy.
"""

from __future__ import annotations

from dataclasses import dataclass

import clang.cindex as cx

from mojo_bindgen.ir import Field, IntType, Struct, StructRef, Type
from mojo_bindgen.parsing.diagnostics import ParserDiagnosticSink
from mojo_bindgen.parsing.lowering.type_lowering import TypeContext, TypeLowerer
from mojo_bindgen.parsing.registry import RecordRegistry

_RECORD_DECL_KINDS = (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL)


@dataclass(frozen=True)
class FieldSite:
    """Normalized description of one physical field site in a record."""

    name: str
    source_name: str
    field_type: cx.Type
    field_cursor: cx.Cursor | None
    byte_offset: int
    is_anonymous: bool
    is_bitfield: bool = False
    bit_offset: int = -1
    bit_width: int | None = None
    attached_record: cx.Cursor | None = None
    uses_attached_record_ref: bool = False


class _FieldDiscovery:
    """Discover normalized field sites for one record definition."""

    def __init__(self, registry: RecordRegistry) -> None:
        """Store the registry used for stable decl IDs and record naming."""
        self.registry = registry

    def discover(self, record_cursor: cx.Cursor) -> list[FieldSite]:
        """Collect field declarations and direct anonymous record members under the record."""
        parent_type = record_cursor.type
        sites: list[FieldSite] = []
        for child in record_cursor.get_children():
            if child.kind == cx.CursorKind.FIELD_DECL:
                sites.append(self._field_decl_site(parent_type, child))
                continue
            if self._is_direct_anonymous_record_member(record_cursor, child):
                site = self._direct_anonymous_record_site(parent_type, child)
                if site is not None:
                    sites.append(site)
        return sites

    def _field_decl_site(self, parent_type: cx.Type, field_cursor: cx.Cursor) -> FieldSite:
        """Build a field site for one field declaration, including bitfields and inline records."""
        name = field_cursor.spelling
        bit_offset = self._field_bit_offset(parent_type, field_cursor)
        byte_offset = bit_offset // 8 if bit_offset >= 0 else 0
        attached = self._attached_inline_record_definition(field_cursor)

        if field_cursor.is_bitfield():
            return FieldSite(
                name=name,
                source_name=name,
                field_type=field_cursor.type,
                field_cursor=field_cursor,
                byte_offset=byte_offset,
                is_anonymous=not bool(name),
                is_bitfield=True,
                bit_offset=max(bit_offset, 0),
                bit_width=field_cursor.get_bitfield_width(),
            )

        return FieldSite(
            name=name,
            source_name=name,
            field_type=field_cursor.type,
            field_cursor=field_cursor,
            byte_offset=byte_offset,
            is_anonymous=not bool(name),
            attached_record=attached,
            uses_attached_record_ref=(
                attached is not None and self._field_type_matches_record(field_cursor, attached)
            ),
        )

    def _direct_anonymous_record_site(
        self,
        parent_type: cx.Type,
        record_cursor: cx.Cursor,
    ) -> FieldSite | None:
        """Build a field site for an anonymous struct/union that is a direct member without a name."""
        implicit_field = self._find_implicit_record_field(parent_type, record_cursor)
        bit_offset = self._field_bit_offset(parent_type, implicit_field)
        byte_offset = bit_offset // 8 if bit_offset >= 0 else 0
        field_type = implicit_field.type if implicit_field is not None else record_cursor.type
        return FieldSite(
            name="",
            source_name="",
            field_type=field_type,
            field_cursor=implicit_field,
            byte_offset=byte_offset,
            is_anonymous=True,
            attached_record=record_cursor,
            uses_attached_record_ref=True,
        )

    @staticmethod
    def _attached_inline_record_definition(field_cursor: cx.Cursor) -> cx.Cursor | None:
        """Return the nested struct/union definition cursor under a field, if any."""
        for child in field_cursor.get_children():
            if child.kind in _RECORD_DECL_KINDS and child.is_definition():
                return child
        return None

    def _is_direct_anonymous_record_member(
        self,
        parent_cursor: cx.Cursor,
        child_cursor: cx.Cursor,
    ) -> bool:
        """Whether the child is an anonymous record member without a separate field declaration."""
        return (
            child_cursor.kind in _RECORD_DECL_KINDS
            and child_cursor.is_definition()
            and self.registry.record_naming(child_cursor).is_anonymous
            and not self._has_explicit_field_for_record(parent_cursor, child_cursor)
        )

    def _has_explicit_field_for_record(
        self,
        parent_cursor: cx.Cursor,
        record_cursor: cx.Cursor,
    ) -> bool:
        """Whether the parent already has a named field whose record type refers to the nested record."""
        target_decl_id = self.registry.decl_id_for_cursor(record_cursor)
        for child in parent_cursor.get_children():
            if child.kind != cx.CursorKind.FIELD_DECL:
                continue
            field_type = child.type.get_canonical()
            if field_type.kind != cx.TypeKind.RECORD:
                continue
            definition = field_type.get_declaration().get_definition()
            if definition is None:
                continue
            if self.registry.decl_id_for_cursor(definition) == target_decl_id:
                return True
        return False

    def _find_implicit_record_field(
        self,
        parent_type: cx.Type,
        record_cursor: cx.Cursor,
    ) -> cx.Cursor | None:
        """Find the field cursor Clang exposes for an anonymous record member, if present."""
        target_decl_id = self.registry.decl_id_for_cursor(record_cursor)
        for field_cursor in parent_type.get_fields():
            field_type = field_cursor.type.get_canonical()
            if field_type.kind != cx.TypeKind.RECORD:
                continue
            definition = field_type.get_declaration().get_definition()
            if definition is None:
                continue
            if self.registry.decl_id_for_cursor(definition) == target_decl_id:
                return field_cursor
        return None

    def _field_type_matches_record(self, field_cursor: cx.Cursor, record_cursor: cx.Cursor) -> bool:
        """Whether the field's record type is the same definition as the given record cursor."""
        field_type = field_cursor.type.get_canonical()
        if field_type.kind != cx.TypeKind.RECORD:
            return False
        definition = field_type.get_declaration().get_definition()
        if definition is None:
            return False
        return self.registry.decl_id_for_cursor(definition) == self.registry.decl_id_for_cursor(
            record_cursor
        )

    @staticmethod
    def _field_bit_offset(parent_type: cx.Type, cursor: cx.Cursor | None) -> int:
        """Bit offset of the field within the parent type, or -1 if unavailable."""
        if cursor is None:
            return -1
        if cursor.spelling:
            bit_offset = parent_type.get_offset(cursor.spelling)
            if bit_offset >= 0:
                return bit_offset
        getter = getattr(cursor, "get_field_offsetof", None)
        if callable(getter):
            try:
                return getter()
            except Exception:
                return -1
        return -1


class RecordLowerer:
    """Lower struct/union definitions and field sites into raw IR."""

    def __init__(
        self,
        registry: RecordRegistry,
        diagnostics: ParserDiagnosticSink,
        type_lowerer: TypeLowerer,
    ) -> None:
        """Wire the registry, diagnostics sink, and type lowerer used for record IR."""
        self.registry = registry
        self.diagnostics = diagnostics
        self.type_lowerer = type_lowerer
        self._field_discovery = _FieldDiscovery(registry)
        self._completed_record_decl_ids: list[str] = []

    def make_struct_ref(self, struct: Struct) -> StructRef:
        """Build a stable StructRef from one lowered Struct."""
        return self.registry.make_struct_ref(struct)

    def lower_top_level_record(self, cursor: cx.Cursor) -> Struct | None:
        """Lower one top-level named record declaration from the primary file."""
        if cursor.kind not in _RECORD_DECL_KINDS:
            return None
        if cursor.is_definition() and cursor.spelling:
            return self.lower_record_definition(cursor)
        if cursor.spelling and not self.registry.is_complete_record_decl(cursor):
            decl_id = self.registry.decl_id_for_cursor(cursor)
            return Struct(
                decl_id=decl_id,
                name=cursor.spelling,
                c_name=cursor.spelling,
                fields=[],
                size_bytes=0,
                align_bytes=0,
                is_union=(cursor.kind == cx.CursorKind.UNION_DECL),
                is_complete=False,
            )
        return None

    def completed_records_since(self, start: int) -> tuple[int, list[Struct | None]]:
        """Return lowered record definitions completed after one marker index."""
        decl_ids = self._completed_record_decl_ids[start:]
        return len(self._completed_record_decl_ids), [
            self.registry.get(decl_id)
            for decl_id in decl_ids
            if self.registry.get(decl_id) is not None
        ]

    def lower_record_definition(self, cursor: cx.Cursor) -> Struct:
        """Lower one complete struct/union definition exactly once."""
        decl_id = self.registry.decl_id_for_cursor(cursor)
        cached = self.registry.get(decl_id)
        if cached is not None:
            return cached

        naming = self.registry.record_naming(cursor)
        record = Struct(
            decl_id=decl_id,
            name=naming.name,
            c_name=naming.c_name,
            fields=[],
            size_bytes=max(0, cursor.type.get_size()),
            align_bytes=max(1, cursor.type.get_align()),
            is_union=cursor.kind == cx.CursorKind.UNION_DECL,
            is_anonymous=naming.is_anonymous,
        )
        self.registry.store(record)

        record.fields = [
            field
            for field in (
                self._lower_field_site(site) for site in self._field_discovery.discover(cursor)
            )
            if field is not None
        ]
        self._apply_attributes(record, cursor)
        if record.decl_id not in self._completed_record_decl_ids:
            self._completed_record_decl_ids.append(record.decl_id)
        return record

    def _lower_field_site(self, site: FieldSite) -> Field | None:
        """Lower one normalized field site into one IR field."""
        if site.is_bitfield:
            backing = self.type_lowerer.lower(site.field_type, TypeContext.FIELD)
            if not isinstance(backing, IntType):
                return None
            return Field(
                name=site.name,
                source_name=site.source_name,
                type=backing,
                byte_offset=site.byte_offset,
                is_anonymous=site.is_anonymous,
                is_bitfield=True,
                bit_offset=site.bit_offset,
                bit_width=site.bit_width,
            )

        field_type = self._lower_field_site_type(site)
        return Field(
            name=site.name,
            source_name=site.source_name,
            type=field_type,
            byte_offset=site.byte_offset,
            is_anonymous=site.is_anonymous,
        )

    def _lower_field_site_type(self, site: FieldSite) -> Type:
        """Lower the type of one normalized field site."""
        if site.attached_record is not None:
            inner = self.lower_record_definition(site.attached_record)
            if site.uses_attached_record_ref:
                return self.make_struct_ref(inner)
        return self.type_lowerer.lower(
            site.field_type,
            TypeContext.FIELD,
            source_cursor=site.field_cursor,
        )

    @staticmethod
    def _apply_attributes(record: Struct, cursor: cx.Cursor) -> None:
        """Set packed and requested alignment on the struct from Clang attribute children."""
        packed = False
        requested_align: int | None = None
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PACKED_ATTR:
                packed = True
            elif child.kind == cx.CursorKind.ALIGNED_ATTR:
                requested_align = record.align_bytes
        if requested_align is None:
            try:
                token_spellings = tuple(token.spelling for token in cursor.get_tokens())
            except Exception:
                token_spellings = ()
            if any(spelling in {"_Alignas", "alignas"} for spelling in token_spellings):
                requested_align = record.align_bytes
        record.is_packed = packed
        record.requested_align_bytes = requested_align
