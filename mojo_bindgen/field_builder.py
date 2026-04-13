"""Build one struct/union field from a FIELD_DECL cursor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import clang.cindex as cx

from mojo_bindgen.ir import Field, Primitive, Struct, StructRef, Type
from mojo_bindgen.type_builder import TypeBuilder, TypeContext
from mojo_bindgen.type_resolver import TypeResolver


@dataclass
class FieldBuildResult:
    field: Field | None
    nested: list[Struct]


class FieldBuilder:
    def __init__(
        self,
        *,
        parent_type: cx.Type,
        cursor: cx.Cursor,
        resolver: TypeResolver,
        build_struct_cb: Callable[[cx.Cursor, list[Struct] | None], Struct | None],
    ) -> None:
        self.parent_type = parent_type
        self.cursor = cursor
        self.resolver = resolver
        self.build_struct_cb = build_struct_cb
        self.type_builder = TypeBuilder(resolver)
        self.nested: list[Struct] = []

    def build(self) -> FieldBuildResult:
        if self.cursor.kind != cx.CursorKind.FIELD_DECL:
            return FieldBuildResult(field=None, nested=[])

        field_name = self.cursor.spelling
        bit_offset, byte_offset = self._compute_offset(field_name)

        if self.cursor.is_bitfield():
            field = self._build_bitfield(field_name, bit_offset, byte_offset)
        else:
            field = Field(
                name=field_name,
                type=self._resolve_type(),
                byte_offset=byte_offset,
            )

        return FieldBuildResult(field=field, nested=self.nested)

    def _compute_offset(self, name: str) -> tuple[int, int]:
        bit_offset = self.parent_type.get_offset(name) if name else -1
        byte_offset = bit_offset // 8 if bit_offset >= 0 else 0
        return bit_offset, byte_offset

    def _build_bitfield(
        self, name: str, bit_offset: int, byte_offset: int
    ) -> Field | None:
        backing = self.type_builder.build(self.cursor.type, TypeContext.FIELD)
        if not isinstance(backing, Primitive):
            return None
        return Field(
            name=name,
            type=backing,
            byte_offset=byte_offset,
            is_bitfield=True,
            bit_offset=max(bit_offset, 0),
            bit_width=self.cursor.get_bitfield_width(),
        )

    def _resolve_type(self) -> Type:
        ft = self.cursor.type.get_canonical()
        if ft.kind != cx.TypeKind.RECORD:
            return self.type_builder.build(self.cursor.type, TypeContext.FIELD)

        decl = ft.get_declaration()
        def_c = decl.get_definition()
        is_anon_record = (
            def_c is not None
            and not decl.spelling
            and def_c.kind in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL)
        )
        if not is_anon_record:
            return self.type_builder.build(self.cursor.type, TypeContext.FIELD)

        inner = self.build_struct_cb(def_c, None)
        if inner is None:
            return self.type_builder.build(self.cursor.type, TypeContext.FIELD)

        self.nested.append(inner)
        return StructRef(
            name=inner.name,
            c_name=inner.c_name,
            is_union=inner.is_union,
            size_bytes=inner.size_bytes,
        )
