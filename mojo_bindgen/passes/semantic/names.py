"""Name-collection helpers for semantic emission planning."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.ir import Enum, Struct, Typedef, Unit


def emitted_struct_enum_names(
    unit: Unit,
    ordered_structs: tuple[Struct, ...],
    incomplete_structs: tuple[Struct, ...],
) -> frozenset[str]:
    emitted_names: set[str] = set()
    for struct_decl in ordered_structs:
        emitted_names.add(mojo_ident(struct_decl.name.strip() or struct_decl.c_name.strip()))
    for struct_decl in incomplete_structs:
        emitted_names.add(mojo_ident(struct_decl.name.strip() or struct_decl.c_name.strip()))
    for decl in unit.decls:
        if isinstance(decl, Enum):
            emitted_names.add(mojo_ident(decl.name))
    return frozenset(emitted_names)


def emitted_typedef_mojo_names(
    unit: Unit, emitted_struct_enum_names: frozenset[str]
) -> frozenset[str]:
    return frozenset(
        mojo_ident(decl.name)
        for decl in unit.decls
        if isinstance(decl, Typedef) and mojo_ident(decl.name) not in emitted_struct_enum_names
    )


@dataclass(frozen=True)
class EmissionNameFacts:
    emitted_names: frozenset[str]
    emitted_typedef_names: frozenset[str]


class CollectEmissionNamesPass:
    """Collect emitted Mojo-visible declaration names."""

    def run(
        self,
        unit: Unit,
        *,
        ordered_structs: tuple[Struct, ...],
        incomplete_structs: tuple[Struct, ...],
    ) -> EmissionNameFacts:
        emitted_names = emitted_struct_enum_names(unit, ordered_structs, incomplete_structs)
        return EmissionNameFacts(
            emitted_names=emitted_names,
            emitted_typedef_names=emitted_typedef_mojo_names(unit, emitted_names),
        )
