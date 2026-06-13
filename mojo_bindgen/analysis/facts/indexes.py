"""Shared declaration indexes for normalized CIR units."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.ir import Const, Enum, Function, GlobalVar, MacroDecl, Struct, Typedef, Unit


@dataclass(frozen=True)
class DeclIndexes:
    """Common lookup maps for top-level declarations."""

    records_by_decl_id: dict[str, Struct]
    typedefs_by_decl_id: dict[str, Typedef]
    enums_by_decl_id: dict[str, Enum]
    functions_by_decl_id: dict[str, Function]
    globals_by_decl_id: dict[str, GlobalVar]
    consts_by_name: dict[str, Const]
    macros_by_name: dict[str, MacroDecl]


def build_decl_indexes(unit: Unit) -> DeclIndexes:
    """Build declaration lookup maps used by analysis and mapping."""

    records_by_decl_id: dict[str, Struct] = {}
    typedefs_by_decl_id: dict[str, Typedef] = {}
    enums_by_decl_id: dict[str, Enum] = {}
    functions_by_decl_id: dict[str, Function] = {}
    globals_by_decl_id: dict[str, GlobalVar] = {}
    consts_by_name: dict[str, Const] = {}
    macros_by_name: dict[str, MacroDecl] = {}

    for decl in unit.decls:
        if isinstance(decl, Struct):
            records_by_decl_id[decl.decl_id] = decl
        elif isinstance(decl, Typedef):
            typedefs_by_decl_id[decl.decl_id] = decl
        elif isinstance(decl, Enum):
            enums_by_decl_id[decl.decl_id] = decl
        elif isinstance(decl, Function):
            functions_by_decl_id[decl.decl_id] = decl
        elif isinstance(decl, GlobalVar):
            globals_by_decl_id[decl.decl_id] = decl
        elif isinstance(decl, Const):
            consts_by_name[decl.name] = decl
        elif isinstance(decl, MacroDecl):
            macros_by_name[decl.name] = decl

    return DeclIndexes(
        records_by_decl_id=records_by_decl_id,
        typedefs_by_decl_id=typedefs_by_decl_id,
        enums_by_decl_id=enums_by_decl_id,
        functions_by_decl_id=functions_by_decl_id,
        globals_by_decl_id=globals_by_decl_id,
        consts_by_name=consts_by_name,
        macros_by_name=macros_by_name,
    )


def record_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map every record ``decl_id`` to its CIR declaration, including unions."""

    return build_decl_indexes(unit).records_by_decl_id


def struct_by_decl_id(unit: Unit) -> dict[str, Struct]:
    """Map non-union struct ``decl_id`` to its CIR declaration."""

    return {
        decl_id: record
        for decl_id, record in build_decl_indexes(unit).records_by_decl_id.items()
        if not record.is_union
    }


__all__ = [
    "DeclIndexes",
    "build_decl_indexes",
    "record_by_decl_id",
    "struct_by_decl_id",
]
