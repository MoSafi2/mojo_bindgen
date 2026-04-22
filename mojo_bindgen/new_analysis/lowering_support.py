"""Small shared helpers for the active CIR -> MojoIR lowering pipeline."""

from __future__ import annotations

from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.ir import Field, Struct, Type, Unit
from mojo_bindgen.mojo_ir import (
    BuiltinType,
    LoweringNote,
    LoweringSeverity,
    MojoBuiltin,
    MojoType,
)
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass, TypeLoweringError


def record_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map every record ``decl_id`` to its CIR declaration, including unions."""

    out: dict[str, Struct] = {}
    for decl in unit.decls:
        if isinstance(decl, Struct):
            out[decl.decl_id] = decl
    return out


def field_display_name(field: Field, index: int) -> str:
    """Best-effort human-facing name for diagnostics."""

    source_name = field.source_name.strip()
    if source_name:
        return source_name
    name = field.name.strip()
    if name:
        return name
    return f"field_{index}"


def record_name(decl: Struct) -> str:
    """Lowered Mojo-facing record name."""

    raw_name = decl.name.strip() or decl.c_name.strip()
    fallback = "anonymous_union" if decl.is_union else "anonymous_struct"
    return mojo_ident(raw_name, fallback=fallback)


def lowering_note(message: str, *, category: str) -> LoweringNote:
    return LoweringNote(
        severity=LoweringSeverity.NOTE,
        message=message,
        category=category,
    )


def stub_note(message: str) -> LoweringNote:
    return lowering_note(message, category="stub_lowering")


def struct_note(message: str) -> LoweringNote:
    return lowering_note(message, category="struct_lowering")


def union_note(message: str) -> LoweringNote:
    return lowering_note(message, category="union_lowering")


def try_lower_type(
    type_lowerer: LowerTypePass,
    t: Type,
    *,
    subject: str,
    failure_suffix: str,
) -> tuple[MojoType | None, str | None]:
    """Lower one CIR type and turn lowering failure into a diagnostic reason."""

    try:
        lowered = type_lowerer.run(t)
    except TypeLoweringError as exc:
        return None, f"{subject} could not be lowered ({exc}); {failure_suffix}"
    if lowered == BuiltinType(MojoBuiltin.UNSUPPORTED):
        return None, f"{subject} lowered to an unsupported Mojo type; {failure_suffix}"
    return lowered, None


__all__ = [
    "field_display_name",
    "lowering_note",
    "record_by_decl_id",
    "record_name",
    "struct_note",
    "stub_note",
    "try_lower_type",
    "union_note",
]
