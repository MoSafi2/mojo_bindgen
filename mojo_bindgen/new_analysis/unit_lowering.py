"""High-level lowering entrypoint from CIR ``Unit`` to MojoIR ``MojoModule``.

This module is intentionally thin. It mirrors the parser's orchestration shape:
one pass owns the overall walk over top-level declarations and delegates
declaration-family lowering to narrower helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.layout import build_register_passable_map, struct_by_decl_id
from mojo_bindgen.analysis.type_walk import TypeWalkOptions, collect_type_nodes
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    BinaryExpr,
    CastExpr,
    Const,
    ConstExpr,
    Decl,
    Enum,
    Function,
    GlobalVar,
    MacroDecl,
    NullPtrLiteral,
    RefExpr,
    SizeOfExpr,
    Struct,
    Type,
    Typedef,
    TypeRef,
    UnaryExpr,
    Unit,
)
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    BuiltinType,
    CallbackType,
    CallTarget,
    EnumDecl,
    EnumMember,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    GlobalKind,
    LinkMode,
    MojoBinaryExpr,
    MojoBuiltin,
    MojoCastExpr,
    MojoConstExpr,
    MojoDecl,
    MojoIntLiteral,
    MojoModule,
    MojoUnaryExpr,
    Param,
    ParametricBase,
    ParametricType,
)
from mojo_bindgen.new_analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
)
from mojo_bindgen.new_analysis.lowering_support import (
    lowering_note,
    record_by_decl_id,
    stub_note,
)
from mojo_bindgen.new_analysis.struct_lowering import (
    LowerStructPass,
    StructLoweringContext,
)
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass
from mojo_bindgen.new_analysis.union_lowering import LowerUnionPass


class UnitLoweringError(ValueError):
    """Raised when a CIR declaration cannot be lowered to MojoIR."""


@dataclass(frozen=True)
class LoweringSession:
    """Immutable collaborators shared across one ``Unit`` lowering run."""

    unit: Unit
    options: MojoEmitOptions
    type_lowerer: LowerTypePass
    const_lowerer: LowerConstExprPass
    struct_context: StructLoweringContext


class UnitDeclLowerer:
    """Lower one top-level CIR declaration into one or more MojoIR declarations."""

    def __init__(self, session: LoweringSession) -> None:
        self.session = session
        self._struct_lowerer = LowerStructPass()
        self._union_lowerer = LowerUnionPass(type_lowerer=session.type_lowerer)

    def lower_decl(self, decl: Decl) -> MojoDecl | list[MojoDecl] | None:
        if isinstance(decl, Typedef):
            return self._lower_typedef(decl)
        if isinstance(decl, Enum):
            return self._lower_enum(decl)
        if isinstance(decl, Function):
            return self._lower_function(decl)
        if isinstance(decl, GlobalVar):
            return self._lower_global(decl)
        if isinstance(decl, Const):
            return self._lower_const(decl)
        if isinstance(decl, MacroDecl):
            return self._lower_macro(decl)
        if isinstance(decl, Struct):
            return self._lower_struct(decl)
        raise UnitLoweringError(f"unsupported CIR declaration node: {type(decl).__name__!r}")

    def _lower_typedef(self, decl: Typedef) -> AliasDecl | None:
        alias_name = mojo_ident(decl.name)
        lowered_type = self.session.type_lowerer.run(decl.aliased)
        if isinstance(lowered_type, CallbackType):
            return AliasDecl(
                name=alias_name,
                kind=AliasKind.CALLBACK_SIGNATURE,
                type_value=lowered_type,
            )
        if getattr(lowered_type, "name", None) == alias_name:
            return None
        return AliasDecl(
            name=alias_name,
            kind=AliasKind.TYPE_ALIAS,
            type_value=lowered_type,
        )

    def _lower_enum(self, decl: Enum) -> EnumDecl:
        return EnumDecl(
            name=mojo_ident(decl.name),
            underlying_type=self.session.type_lowerer.run(decl.underlying),
            align_decorator=None,
            fieldwise_init=True,
            enumerants=[
                EnumMember(name=mojo_ident(member.name), value=member.value)
                for member in decl.enumerants
            ],
        )

    def _lower_function(self, decl: Function) -> FunctionDecl:
        return FunctionDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            params=[
                Param(
                    name=(mojo_ident(param.name, fallback=f"a{i}") if param.name else f"a{i}"),
                    type=self.session.type_lowerer.run(param.type),
                )
                for i, param in enumerate(decl.params)
            ],
            return_type=self.session.type_lowerer.run(decl.ret),
            kind=(FunctionKind.VARIADIC_STUB if decl.is_variadic else FunctionKind.WRAPPER),
            call_target=CallTarget(
                link_mode=_link_mode_for_options(self.session.options),
                symbol=decl.link_name,
            ),
        )

    def _lower_global(self, decl: GlobalVar) -> GlobalDecl:
        lowered_type = self.session.type_lowerer.run(decl.type)
        is_atomic = (
            isinstance(lowered_type, ParametricType) and lowered_type.base == ParametricBase.ATOMIC
        )
        return GlobalDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            value_type=lowered_type,
            is_const=decl.is_const,
            kind=(GlobalKind.STUB if is_atomic else GlobalKind.WRAPPER),
        )

    def _lower_const(self, decl: Const) -> AliasDecl:
        try:
            value = self.session.const_lowerer.run(decl.expr)
        except ConstExprLoweringError:
            return AliasDecl(
                name=mojo_ident(decl.name),
                kind=AliasKind.CONST_VALUE,
                diagnostics=[
                    stub_note("constant expression could not be lowered; placeholder alias emitted")
                ],
            )
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.CONST_VALUE,
            const_value=self._typed_const_value(value, decl.type),
        )

    def _lower_macro(self, decl: MacroDecl) -> AliasDecl:
        if decl.expr is not None and decl.type is not None:
            if isinstance(decl.expr, RefExpr):
                return self._macro_comment_alias(
                    decl,
                    f"macro {decl.name}: identifier reference macro is not emitted directly; only literal macros are currently supported",
                )
            try:
                value = self.session.const_lowerer.run(decl.expr)
            except ConstExprLoweringError:
                if isinstance(decl.expr, NullPtrLiteral):
                    return self._macro_comment_alias(
                        decl,
                        f"macro {decl.name}: null pointer macro is not emitted directly",
                    )
                value = None
            else:
                return AliasDecl(
                    name=mojo_ident(decl.name),
                    kind=AliasKind.MACRO_VALUE,
                    const_value=self._typed_const_value(value, decl.type),
                )
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.MACRO_VALUE,
            diagnostics=(
                self._macro_comment_notes(
                    decl,
                    f"macro {decl.name}: {decl.diagnostic}",
                )
                if decl.diagnostic
                else [stub_note("macro lowering is incomplete; placeholder alias emitted")]
            ),
        )

    def _lower_struct(self, decl: Struct) -> MojoDecl:
        if decl.is_union:
            return self._union_lowerer.run(decl)
        return self._struct_lowerer.run(decl, context=self.session.struct_context)

    def _typed_const_value(self, value: MojoConstExpr, decl_type) -> MojoConstExpr:
        lowered_type = self.session.type_lowerer.run(decl_type)
        if isinstance(lowered_type, BuiltinType) and lowered_type.name in {
            MojoBuiltin.C_CHAR,
            MojoBuiltin.C_UCHAR,
            MojoBuiltin.C_SHORT,
            MojoBuiltin.C_USHORT,
            MojoBuiltin.C_INT,
            MojoBuiltin.C_UINT,
            MojoBuiltin.C_LONG,
            MojoBuiltin.C_ULONG,
            MojoBuiltin.C_LONG_LONG,
            MojoBuiltin.C_ULONG_LONG,
            MojoBuiltin.INT128,
            MojoBuiltin.UINT128,
        }:
            return self._coerce_integral_const(value, lowered_type)
        return value

    def _coerce_integral_const(
        self,
        value: MojoConstExpr,
        lowered_type: BuiltinType,
    ) -> MojoConstExpr:
        if isinstance(value, MojoIntLiteral):
            return MojoCastExpr(target=lowered_type, expr=value)
        if isinstance(value, MojoUnaryExpr):
            return MojoUnaryExpr(
                op=value.op,
                operand=self._coerce_integral_const(value.operand, lowered_type),
            )
        if isinstance(value, MojoBinaryExpr):
            return MojoBinaryExpr(
                op=value.op,
                lhs=self._coerce_integral_const(value.lhs, lowered_type),
                rhs=self._coerce_integral_const(value.rhs, lowered_type),
            )
        return value

    def _macro_comment_alias(self, decl: MacroDecl, message: str) -> AliasDecl:
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.MACRO_VALUE,
            diagnostics=self._macro_comment_notes(decl, message),
        )

    def _macro_comment_notes(self, decl: MacroDecl, message: str):
        return [
            lowering_note(message, category="macro_comment"),
            lowering_note(
                f"define {decl.name} {' '.join(decl.tokens)}",
                category="macro_comment",
            ),
        ]


class LowerUnitPass:
    """Lower an already-normalized CIR ``Unit`` into a MojoIR ``MojoModule``."""

    def __init__(self, options: MojoEmitOptions | None = None) -> None:
        self._options = options or MojoEmitOptions()

    def run(self, unit: Unit) -> MojoModule:
        type_lowerer = LowerTypePass()
        record_map = record_by_decl_id(unit)
        struct_map = struct_by_decl_id(unit)
        session = LoweringSession(
            unit=unit,
            options=self._options,
            type_lowerer=type_lowerer,
            const_lowerer=LowerConstExprPass(type_lowering=type_lowerer),
            struct_context=StructLoweringContext(
                record_map=record_map,
                register_passable_by_decl_id=build_register_passable_map(struct_map),
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


def _walk_typeref_nodes(t: Type, out: list[TypeRef]) -> None:
    out.extend(
        node
        for node in collect_type_nodes(
            t,
            lambda node: isinstance(node, TypeRef),
            options=TypeWalkOptions(descend_vector_element=True),
        )
        if isinstance(node, TypeRef)
    )


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


def _link_mode_for_options(options: MojoEmitOptions) -> LinkMode:
    if options.linking == "owned_dl_handle":
        return LinkMode.OWNED_DL_HANDLE
    return LinkMode.EXTERNAL_CALL


__all__ = [
    "LowerUnitPass",
    "LoweringSession",
    "UnitDeclLowerer",
    "UnitLoweringError",
    "lower_unit",
]
