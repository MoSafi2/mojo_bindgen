"""High-level mapping entrypoint from CIR ``Unit`` to MojoIR ``MojoModule``.

This module is intentionally thin. It mirrors the parser's orchestration shape:
one pass owns the overall walk over top-level declarations and delegates
declaration-family mapping to narrower helpers.
"""

from __future__ import annotations

from mojo_bindgen.analysis.facts.context import AnalysisContext, build_analysis_context
from mojo_bindgen.analysis.mojo.alias_mapping import map_typedef_alias
from mojo_bindgen.analysis.mojo.const_expr_mapping import (
    MapConstExprPass,
)
from mojo_bindgen.analysis.mojo.decl_mapping import (
    MappingSession,
    UnitDeclMapper,
    _link_mode_for_options,
)
from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.mojo.struct_mapping import (
    StructMappingContext,
)
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.ir import (
    MojoDecl,
    MojoModule,
    Unit,
)


class MapUnitPass:
    """Map an already-normalized CIR ``Unit`` into a MojoIR ``MojoModule``."""

    def __init__(
        self,
        options: MojoEmitOptions | None = None,
        *,
        context: AnalysisContext | None = None,
    ) -> None:
        self._options = options or MojoEmitOptions()
        self._context = context

    def run(self, unit: Unit) -> MojoModule:
        context = self._context or build_analysis_context(unit)
        if context.unit is not unit:
            context = build_analysis_context(unit)
        type_mapper = MapTypePass()
        session = MappingSession(
            unit=unit,
            options=self._options,
            type_mapper=type_mapper,
            const_expr_mapper=MapConstExprPass(type_mapping=type_mapper),
            struct_context=StructMappingContext(
                record_map=context.records_by_decl_id,
                record_layouts=context.record_layouts,
                record_storage=context.record_storage,
                target_abi=unit.target_abi,
                type_mapper=type_mapper,
            ),
        )
        decl_mapping = UnitDeclMapper(session)
        mapped_decls = self._synth_external_typedef_aliases(context, type_mapper)
        for decl in unit.decls:
            mapped = decl_mapping.map_decl(decl)
            if mapped is None:
                continue
            if isinstance(mapped, list):
                mapped_decls.extend(mapped)
            else:
                mapped_decls.append(mapped)
        return MojoModule(
            source_header=unit.source_header,
            library=unit.library,
            link_name=unit.link_name,
            link_mode=_link_mode_for_options(self._options),
            library_path_hint=self._options.library_path_hint,
            decls=mapped_decls,
        )

    def _synth_external_typedef_aliases(
        self,
        context: AnalysisContext,
        type_mapper: MapTypePass,
    ) -> list[MojoDecl]:
        mapped: list[MojoDecl] = []
        for ref in context.alias_classification.external_type_refs_by_decl_id.values():
            alias = map_typedef_alias(
                c_name=ref.name,
                aliased=ref.canonical,
                type_mapper=type_mapper,
            )
            if alias is None:
                continue
            mapped.append(alias)
        return mapped


def map_unit(
    unit: Unit,
    *,
    options: MojoEmitOptions | None = None,
    context: AnalysisContext | None = None,
) -> MojoModule:
    """Map one CIR ``Unit`` into a standalone ``MojoModule``."""

    return MapUnitPass(options=options, context=context).run(unit)


__all__ = [
    "MapUnitPass",
    "map_unit",
]
