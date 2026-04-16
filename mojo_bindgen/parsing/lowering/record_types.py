"""Record caching and record-type resolution for parser lowering.

This module owns the shared record repository and the policy for resolving
clang record types into IR references or inline lowered definitions. It exists
to keep type lowering and record-definition lowering from mutating each
other's internals directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import clang.cindex as cx

from mojo_bindgen.ir import OpaqueRecordRef, Struct, StructRef, Type, UnsupportedType
from mojo_bindgen.parsing.index import DeclIndex


@dataclass
class RecordRepository:
    """Own cached lowered record definitions and stable struct-ref creation."""

    _records_by_decl_id: dict[str, Struct] = field(default_factory=dict)

    def get(self, decl_id: str) -> Struct | None:
        """Return a cached lowered record definition when available."""
        return self._records_by_decl_id.get(decl_id)

    def store(self, struct: Struct) -> None:
        """Store a lowered record definition by declaration id."""
        self._records_by_decl_id[struct.decl_id] = struct

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


@dataclass
class RecordTypeResolver:
    """Resolve record-typed clang nodes without lowerers owning each other."""

    index: DeclIndex
    repository: RecordRepository
    _definition_lowerer: Callable[[cx.Cursor], tuple[list[Struct], Struct]] | None = None

    def bind_definition_lowerer(
        self,
        lower_record_definition: Callable[[cx.Cursor], tuple[list[Struct], Struct]],
    ) -> None:
        """Attach the record-definition lowerer used for inline record definitions."""
        self._definition_lowerer = lower_record_definition

    def lower_record_type(self, clang_type: cx.Type) -> Type:
        """Resolve one clang record type to an IR record representation."""
        decl = clang_type.get_declaration()
        decl_id = self.index.decl_id_for_cursor(decl)

        cached = self.repository.get(decl_id)
        if cached is not None:
            return self.repository.make_struct_ref(cached)

        definition = self.index.record_definition_for_decl(decl)
        if definition is not None:
            if decl.spelling and decl_id in self.index.top_level_decl_ids:
                return StructRef(
                    decl_id=decl_id,
                    name=decl.spelling,
                    c_name=decl.spelling,
                    is_union=(definition.kind == cx.CursorKind.UNION_DECL),
                    size_bytes=max(0, clang_type.get_size()),
                    is_anonymous=False,
                )
            _, struct = self._require_definition_lowerer()(definition)
            return self.repository.make_struct_ref(struct)

        if decl.spelling:
            return OpaqueRecordRef(
                decl_id=decl_id,
                name=decl.spelling,
                c_name=decl.spelling,
                is_union=(decl.kind == cx.CursorKind.UNION_DECL),
            )
        return UnsupportedType(
            category="unsupported_extension",
            spelling="__anonymous_record",
            reason="anonymous incomplete record reference cannot be named",
        )

    def _require_definition_lowerer(
        self,
    ) -> Callable[[cx.Cursor], tuple[list[Struct], Struct]]:
        if self._definition_lowerer is None:
            raise RuntimeError("RecordTypeResolver definition lowerer has not been bound")
        return self._definition_lowerer
