"""High-level lowering entrypoint from CIR ``Unit`` to MojoIR ``MojoModule``.

This module is intentionally thin. It mirrors the parser's orchestration shape:
one pass owns the overall walk over top-level declarations and delegates
declaration-family lowering to narrower helpers.
"""

from __future__ import annotations

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.const_lowering import (
    LowerConstExprPass,
)
from mojo_bindgen.analysis.decl_lowerer import (
    LoweringSession,
    UnitDeclLowerer,
    _link_mode_for_options,
)
from mojo_bindgen.analysis.lowering_support import (
    record_by_decl_id,
)
from mojo_bindgen.analysis.struct_lowering import (
    StructLoweringContext,
)
from mojo_bindgen.analysis.type_lowering import LowerTypePass
from mojo_bindgen.analysis.type_walk import _walk_typeref_nodes
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    BinaryExpr,
    CastExpr,
    Const,
    ConstExpr,
    Function,
    GlobalVar,
    MacroDecl,
    SizeOfExpr,
    Struct,
    Typedef,
    TypeRef,
    UnaryExpr,
    Unit,
)
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    CallbackType,
    MojoDecl,
    MojoModule,
)


class LowerUnitPass:
    """Lower an already-normalized CIR ``Unit`` into a MojoIR ``MojoModule``."""

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        self._options = options or MojoEmitOptions()

    def run(self, unit: Unit) -> MojoModule:
        type_lowerer = LowerTypePass()
        record_map = record_by_decl_id(unit)
        session = LoweringSession(
            unit=unit,
            options=self._options,
            type_lowerer=type_lowerer,
            const_lowerer=LowerConstExprPass(type_lowering=type_lowerer),
            struct_context=StructLoweringContext(
                record_map=record_map,
                target_abi=unit.target_abi,
                type_lowerer=type_lowerer,
            ),
        )
        decl_lowerer = UnitDeclLowerer(session)
        lowered_decls = self._synth_external_typedef_aliases(unit, type_lowerer)
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
        unit: Unit,
        type_lowerer: LowerTypePass,
    ) -> list[MojoDecl]:
        local_typedef_ids = {decl.decl_id for decl in unit.decls if isinstance(decl, Typedef)}
        seen_typedef_ids: set[str] = set()
        lowered: list[MojoDecl] = []
        for ref in _collect_typeref_uses(unit):
            if ref.decl_id in local_typedef_ids or ref.decl_id in seen_typedef_ids:
                continue
            seen_typedef_ids.add(ref.decl_id)
            alias_name = mojo_ident(ref.name)
            lowered_type = type_lowerer.run(ref.canonical)
            if isinstance(lowered_type, CallbackType):
                lowered.append(
                    AliasDecl(
                        name=alias_name,
                        kind=AliasKind.CALLBACK_SIGNATURE,
                        type_value=lowered_type,
                    )
                )
                continue
            if getattr(lowered_type, "name", None) == alias_name:
                continue
            lowered.append(
                AliasDecl(
                    name=alias_name,
                    kind=AliasKind.TYPE_ALIAS,
                    type_value=lowered_type,
                )
            )
        return lowered


def _walk_const_expr_typerefs(expr: ConstExpr, out: list[TypeRef]) -> None:
    if isinstance(expr, CastExpr):
        _walk_typeref_nodes(expr.target, out)
        _walk_const_expr_typerefs(expr.expr, out)
        return
    if isinstance(expr, SizeOfExpr):
        _walk_typeref_nodes(expr.target, out)
        return
    if isinstance(expr, UnaryExpr):
        _walk_const_expr_typerefs(expr.operand, out)
        return
    if isinstance(expr, BinaryExpr):
        _walk_const_expr_typerefs(expr.lhs, out)
        _walk_const_expr_typerefs(expr.rhs, out)


def _collect_typeref_uses(unit: Unit) -> list[TypeRef]:
    collected: list[TypeRef] = []
    for decl in unit.decls:
        if isinstance(decl, Function):
            _walk_typeref_nodes(decl.ret, collected)
            for param in decl.params:
                _walk_typeref_nodes(param.type, collected)
            continue
        if isinstance(decl, Typedef):
            _walk_typeref_nodes(decl.aliased, collected)
            _walk_typeref_nodes(decl.canonical, collected)
            continue
        if isinstance(decl, Struct):
            for field in decl.fields:
                _walk_typeref_nodes(field.type, collected)
            continue
        if isinstance(decl, GlobalVar):
            _walk_typeref_nodes(decl.type, collected)
            if decl.initializer is not None:
                _walk_const_expr_typerefs(decl.initializer, collected)
            continue
        if isinstance(decl, Const):
            _walk_typeref_nodes(decl.type, collected)
            _walk_const_expr_typerefs(decl.expr, collected)
            continue
        if isinstance(decl, MacroDecl):
            if decl.type is not None:
                _walk_typeref_nodes(decl.type, collected)
            if decl.expr is not None:
                _walk_const_expr_typerefs(decl.expr, collected)
    return collected


def lower_unit(unit: Unit, *, options: MojoEmitOptions | None = None) -> MojoModule:
    """Lower one CIR ``Unit`` into a standalone ``MojoModule``."""

    return LowerUnitPass(options=options).run(unit)


__all__ = [
    "LowerUnitPass",
    "lower_unit",
]
