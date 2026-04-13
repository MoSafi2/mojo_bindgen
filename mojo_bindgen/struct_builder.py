"""Build one struct/union declaration from a definition cursor."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from dataclasses import dataclass

import clang.cindex as cx

from mojo_bindgen.field_builder import FieldBuilder
from mojo_bindgen.ir import Field, Struct
from mojo_bindgen.type_resolver import TypeResolver


@dataclass
class StructBuildResult:
    struct: Struct
    nested: list[Struct]


class StructBuilder:
    def __init__(
        self,
        *,
        cursor: cx.Cursor,
        resolver: TypeResolver,
        build_struct_cb: Callable[[cx.Cursor, list[Struct] | None], Struct | None],
        validate_layout: bool = False,
        debug: bool | None = None,
    ) -> None:
        self.cursor = cursor
        self.resolver = resolver
        self.build_struct_cb = build_struct_cb
        self.validate_layout = validate_layout
        self.debug = (
            os.environ.get("MOJO_BINDGEN_DEBUG_STRUCT_BUILDER", "") == "1"
            if debug is None
            else debug
        )
        self.nested: list[Struct] = []

    def build(self) -> StructBuildResult:
        c_name, name, _ = self._resolve_identity()
        size_bytes, align_bytes = self._compute_layout()
        fields = self._build_fields()
        struct = Struct(
            name=name,
            c_name=c_name,
            fields=fields,
            size_bytes=size_bytes,
            align_bytes=align_bytes,
            is_union=(self.cursor.kind == cx.CursorKind.UNION_DECL),
        )
        self._apply_attributes(struct)
        if self.validate_layout:
            self._validate_layout(struct)
        self._trace(struct)
        return StructBuildResult(struct=struct, nested=self.nested)

    def _resolve_identity(self) -> tuple[str, str, bool]:
        c_name_raw = self.cursor.spelling
        if c_name_raw:
            return c_name_raw, c_name_raw, False
        usr0 = self.cursor.get_usr()
        digest = hashlib.sha256(usr0.encode("utf-8")).hexdigest()[:16]
        synth = f"__bindgen_anon_{digest}"
        return synth, synth, True

    def _compute_layout(self) -> tuple[int, int]:
        t = self.cursor.type
        return max(0, t.get_size()), max(1, t.get_align())

    def _build_fields(self) -> list[Field]:
        fields: list[Field] = []
        for child in self.cursor.get_children():
            if child.kind != cx.CursorKind.FIELD_DECL:
                continue
            result = FieldBuilder(
                parent_type=self.cursor.type,
                cursor=child,
                resolver=self.resolver,
                build_struct_cb=self.build_struct_cb,
            ).build()
            if result.field is not None:
                fields.append(result.field)
            self.nested.extend(result.nested)
        return fields

    def _apply_attributes(self, _struct: Struct) -> None:
        """Extension point for packed/aligned/target-specific attributes."""

    def _validate_layout(self, struct: Struct) -> None:
        for field in struct.fields:
            if field.byte_offset > struct.size_bytes:
                raise ValueError(
                    f"invalid layout for {struct.name}: field {field.name!r} "
                    f"offset {field.byte_offset} exceeds size {struct.size_bytes}"
                )

    def _trace(self, struct: Struct) -> None:
        if self.debug:
            print(
                "[StructBuilder]",
                struct.name,
                f"size={struct.size_bytes}",
                f"align={struct.align_bytes}",
                f"fields={len(struct.fields)}",
            )
