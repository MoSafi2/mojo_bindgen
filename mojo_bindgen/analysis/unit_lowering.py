"""High-level lowering entrypoint from CIR ``Unit`` to MojoIR ``MojoModule``.

This module is intentionally thin. It mirrors the parser's orchestration shape:
one pass owns the overall walk over top-level declarations and delegates
declaration-family lowering to narrower helpers.
"""

from __future__ import annotations

from mojo_bindgen.analysis.alias_lowering import lower_typedef_alias
from mojo_bindgen.analysis.const_lowering import (
    LowerConstExprPass,
)
from mojo_bindgen.analysis.context import AnalysisContext, build_analysis_context
from mojo_bindgen.analysis.decl_lowerer import (
    LoweringSession,
    UnitDeclLowerer,
    _link_mode_for_options,
)
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.struct_lowering import (
    StructLoweringContext,
)
from mojo_bindgen.analysis.type_lowering import LowerTypePass
from mojo_bindgen.ir import (
    MojoDecl,
    MojoModule,
    Unit,
)


class LowerUnitPass:
    """Lower an already-normalized CIR ``Unit`` into a MojoIR ``MojoModule``."""

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
        type_lowerer = LowerTypePass()
        session = LoweringSession(
            unit=unit,
            options=self._options,
            type_lowerer=type_lowerer,
            const_lowerer=LowerConstExprPass(type_lowering=type_lowerer),
            struct_context=StructLoweringContext(
                record_map=context.records_by_decl_id,
                record_layouts=context.record_layouts,
                record_shapes=context.record_shapes,
                target_abi=unit.target_abi,
                type_lowerer=type_lowerer,
            ),
        )
        decl_lowerer = UnitDeclLowerer(session)
        lowered_decls = self._synth_external_typedef_aliases(context, type_lowerer)
        for decl in unit.decls:
            lowered = decl_lowerer.lower_decl(decl)
            if lowered is None:
                continue
            if isinstance(lowered, list):
                lowered_decls.extend(lowered)
            else:
                lowered_decls.append(lowered)
        return MojoModule(
            source_header=unit.source_header,
            library=unit.library,
            link_name=unit.link_name,
            link_mode=_link_mode_for_options(self._options),
            library_path_hint=self._options.library_path_hint,
            decls=lowered_decls,
        )

    def _synth_external_typedef_aliases(
        self,
        context: AnalysisContext,
        type_lowerer: LowerTypePass,
    ) -> list[MojoDecl]:
        lowered: list[MojoDecl] = []
        for ref in context.alias_classification.external_type_refs_by_decl_id.values():
            alias = lower_typedef_alias(
                c_name=ref.name,
                aliased=ref.canonical,
                type_lowerer=type_lowerer,
            )
            if alias is None:
                continue
            lowered.append(alias)
        return lowered


def lower_unit(
    unit: Unit,
    *,
    options: MojoEmitOptions | None = None,
    context: AnalysisContext | None = None,
) -> MojoModule:
    """Lower one CIR ``Unit`` into a standalone ``MojoModule``."""

    return LowerUnitPass(options=options, context=context).run(unit)


__all__ = [
    "LowerUnitPass",
    "lower_unit",
]
