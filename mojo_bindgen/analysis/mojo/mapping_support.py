"""Small shared helpers for the active CIR -> MojoIR mapping pipeline."""

from __future__ import annotations

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.facts.indexes import record_by_decl_id
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass, TypeMappingError
from mojo_bindgen.ir import (
    BuiltinType,
    Field,
    MappingNote,
    MappingSeverity,
    MojoBuiltin,
    Struct,
    Type,
)


def field_display_name(field: Field, index: int) -> str:
    """Best-effort human-facing name for diagnostics."""

    source_name = field.source_name.strip()
    if source_name:
        return source_name
    name = field.name.strip()
    if name:
        return name
    return f"field_{index}"


def field_mojo_name(field: Field, index: int) -> str:
    if field.source_name:
        return mojo_ident(field.source_name)
    if field.name:
        return mojo_ident(field.name)
    return f"_anon_{index}"


def record_name(decl: Struct) -> str:
    """Mapped Mojo-facing record name."""

    raw_name = decl.name.strip() or decl.c_name.strip()
    fallback = "anonymous_union" if decl.is_union else "anonymous_struct"
    return mojo_ident(raw_name, fallback=fallback)


def mapping_note(message: str, *, category: str) -> MappingNote:
    return MappingNote(
        severity=MappingSeverity.NOTE,
        message=message,
        category=category,
    )


def stub_note(message: str) -> MappingNote:
    return mapping_note(message, category="stub_mapping")


def struct_note(message: str) -> MappingNote:
    return mapping_note(message, category="struct_mapping")


def union_note(message: str) -> MappingNote:
    return mapping_note(message, category="union_mapping")


def try_map_type(
    type_mapper: MapTypePass,
    t: Type,
    *,
    subject: str,
    failure_suffix: str,
) -> tuple[Type | None, str | None]:
    """Map one CIR type and turn mapping failure into a diagnostic reason."""

    try:
        mapped = type_mapper.run(t)
    except TypeMappingError as exc:
        return None, f"{subject} could not be mapped ({exc}); {failure_suffix}"
    if mapped == BuiltinType(MojoBuiltin.UNSUPPORTED):
        return None, f"{subject} mapped to an unsupported Mojo type; {failure_suffix}"
    return mapped, None


__all__ = [
    "field_display_name",
    "field_mojo_name",
    "mapping_note",
    "record_by_decl_id",
    "record_name",
    "struct_note",
    "stub_note",
    "try_map_type",
    "union_note",
]
