"""Struct and union lowering for the parser package.

This module owns lowering of record declarations and fields. It may delegate
type conversion to the type lowerer, but it does not assemble unrelated
top-level declarations such as functions, typedefs, or globals.
"""

from __future__ import annotations

import clang.cindex as cx

from mojo_bindgen.ir import Field, IntType, Struct, StructRef, Type
from mojo_bindgen.parsing.diagnostics import ParserDiagnosticSink
from mojo_bindgen.parsing.index import DeclIndex
from mojo_bindgen.parsing.lowering.record_types import RecordRepository
from mojo_bindgen.parsing.lowering.type_lowering import TypeContext, TypeLowerer


class RecordLowerer:
    """Lower record declarations and fields through explicit collaborators."""

    def __init__(
        self,
        index: DeclIndex,
        diagnostics: ParserDiagnosticSink,
        type_lowerer: TypeLowerer,
        repository: RecordRepository,
    ) -> None:
        self.index = index
        self.diagnostics = diagnostics
        self.type_lowerer = type_lowerer
        self.repository = repository

    def make_struct_ref(self, struct: Struct) -> StructRef:
        """Build a stable StructRef from one lowered Struct."""
        return self.repository.make_struct_ref(struct)

    def lower_top_level_record(self, cursor: cx.Cursor) -> list[Struct] | Struct | None:
        """Lower a top-level record declaration from the primary file."""
        if cursor.kind not in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            return None
        if cursor.is_definition() and cursor.spelling:
            nested, struct = self.lower_record_definition(cursor)
            if nested:
                return nested + [struct]
            return struct
        if cursor.spelling and not self.index.is_complete_record_decl(cursor):
            decl_id = self.index.decl_id_for_cursor(cursor)
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

    def lower_record_definition(self, cursor: cx.Cursor) -> tuple[list[Struct], Struct]:
        """Lower a complete struct/union definition and nested anonymous records."""
        decl_id, c_name, name, is_anonymous = self.index.record_lowering_identity(cursor)
        cached = self.repository.get(decl_id)
        if cached is not None:
            return [], cached

        struct = Struct(
            decl_id=decl_id,
            name=name,
            c_name=c_name,
            fields=[],
            size_bytes=max(0, cursor.type.get_size()),
            align_bytes=max(1, cursor.type.get_align()),
            is_union=(cursor.kind == cx.CursorKind.UNION_DECL),
            is_anonymous=is_anonymous,
        )
        self.repository.store(struct)

        nested: list[Struct] = []
        fields: list[Field] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.FIELD_DECL:
                field, nested_defs = self._lower_field(cursor.type, child)
            elif (
                child.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL)
                and child.is_definition()
                and self.index.record_lowering_identity(child)[3]
                and not self._has_explicit_field_for_record(cursor, child)
            ):
                field, nested_defs = self._lower_direct_anonymous_record_field(cursor.type, child)
            else:
                continue
            self._extend_unique_structs(nested, nested_defs)
            if field is not None:
                fields.append(field)
        struct.fields = fields
        self._apply_attributes(struct, cursor)
        return nested, struct

    def _lower_field(self, parent_type: cx.Type, cursor: cx.Cursor) -> tuple[Field | None, list[Struct]]:
        field_name = cursor.spelling
        bit_offset = self._field_bit_offset(parent_type, cursor)
        byte_offset = bit_offset // 8 if bit_offset >= 0 else 0

        if cursor.is_bitfield():
            backing = self.type_lowerer.lower(cursor.type, TypeContext.FIELD)
            if not isinstance(backing, IntType):
                return None, []
            return (
                Field(
                    name=field_name,
                    source_name=field_name,
                    type=backing,
                    byte_offset=byte_offset,
                    is_anonymous=not bool(field_name),
                    is_bitfield=True,
                    bit_offset=max(bit_offset, 0),
                    bit_width=cursor.get_bitfield_width(),
                ),
                [],
            )

        lowered_type, nested = self._lower_field_type(cursor)
        field = Field(
            name=field_name,
            source_name=field_name,
            type=lowered_type,
            byte_offset=byte_offset,
            is_anonymous=not bool(field_name),
        )
        return field, nested

    @staticmethod
    def _extend_unique_structs(target: list[Struct], defs: list[Struct]) -> None:
        seen = {decl.decl_id for decl in target}
        for decl in defs:
            if decl.decl_id in seen:
                continue
            target.append(decl)
            seen.add(decl.decl_id)

    def _lower_direct_anonymous_record_field(
        self,
        parent_type: cx.Type,
        cursor: cx.Cursor,
    ) -> tuple[Field, list[Struct]]:
        """Lower a direct anonymous ``struct { ... };`` / ``union { ... };`` member."""
        implicit_field = self._find_implicit_record_field(parent_type, cursor)
        bit_offset = implicit_field.get_field_offsetof() if implicit_field is not None else -1
        byte_offset = bit_offset // 8 if bit_offset >= 0 else 0
        nested_defs, inner = self.lower_record_definition(cursor)
        return (
            Field(
                name="",
                source_name="",
                type=self.make_struct_ref(inner),
                byte_offset=byte_offset,
                is_anonymous=True,
            ),
            nested_defs + [inner],
        )

    def _lower_field_type(self, cursor: cx.Cursor) -> tuple[Type, list[Struct]]:
        nested_defs = self._field_named_nested_record_defs(cursor)
        ft = cursor.type.get_canonical()
        if ft.kind != cx.TypeKind.RECORD:
            return self.type_lowerer.lower(cursor.type, TypeContext.FIELD), nested_defs

        decl = ft.get_declaration()
        definition = decl.get_definition()
        is_anon_record = (
            definition is not None
            and not decl.spelling
            and definition.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL)
        )
        if not is_anon_record:
            return self.type_lowerer.lower(cursor.type, TypeContext.FIELD), nested_defs

        anon_nested_defs, inner = self.lower_record_definition(definition)
        self._extend_unique_structs(nested_defs, anon_nested_defs + [inner])
        return self.make_struct_ref(inner), nested_defs

    def _field_named_nested_record_defs(self, cursor: cx.Cursor) -> list[Struct]:
        """Return named inline record defs attached to one field declaration."""
        nested: list[Struct] = []
        for child in cursor.get_children():
            if child.kind not in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
                continue
            if not child.is_definition():
                continue
            _, _, _, is_anonymous = self.index.record_lowering_identity(child)
            if is_anonymous:
                continue
            child_nested, struct = self.lower_record_definition(child)
            self._extend_unique_structs(nested, child_nested + [struct])
        return nested

    def _find_implicit_record_field(self, parent_type: cx.Type, record: cx.Cursor) -> cx.Cursor | None:
        """Find the implicit field cursor that stores a direct anonymous record member."""
        record_decl_id = self.index.decl_id_for_cursor(record)
        for field_cursor in parent_type.get_fields():
            definition = field_cursor.type.get_canonical().get_declaration().get_definition()
            if definition is None:
                continue
            if self.index.decl_id_for_cursor(definition) == record_decl_id:
                return field_cursor
        return None

    def _has_explicit_field_for_record(self, parent: cx.Cursor, record: cx.Cursor) -> bool:
        """Return whether ``record`` already has an explicit ``FIELD_DECL`` in ``parent``."""
        record_decl_id = self.index.decl_id_for_cursor(record)
        for child in parent.get_children():
            if child.kind != cx.CursorKind.FIELD_DECL:
                continue
            definition = child.type.get_canonical().get_declaration().get_definition()
            if definition is None:
                continue
            if self.index.decl_id_for_cursor(definition) == record_decl_id:
                return True
        return False

    @staticmethod
    def _field_bit_offset(parent_type: cx.Type, cursor: cx.Cursor) -> int:
        """Return a field bit offset across named, anonymous, and implicit field cursors."""
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

    @staticmethod
    def _apply_attributes(struct: Struct, cursor: cx.Cursor) -> None:
        packed = False
        requested_align: int | None = None
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PACKED_ATTR:
                packed = True
            elif child.kind == cx.CursorKind.ALIGNED_ATTR:
                requested_align = struct.align_bytes
        struct.is_packed = packed
        struct.requested_align_bytes = requested_align
