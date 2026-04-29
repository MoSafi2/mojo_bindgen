from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
)
from mojo_bindgen.analysis.lowering_support import (
    lowering_note,
    stub_note,
)
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.struct_lowering import (
    StructLoweringContext,
    lower_struct,
)
from mojo_bindgen.analysis.type_lowering import LowerTypePass, exact_width_stdint_alias_type
from mojo_bindgen.analysis.union_lowering import LowerUnionPass
from mojo_bindgen.ir import (
    Const,
    Decl,
    Enum,
    Function,
    GlobalVar,
    MacroDecl,
    NullPtrLiteral,
    RefExpr,
    Struct,
    Typedef,
    Unit,
)
from mojo_bindgen.mojo_ir import (
    _MOJO_INT_TYPES,
    AliasDecl,
    AliasKind,
    BuiltinType,
    CallTarget,
    ComptimeMember,
    FunctionDecl,
    FunctionKind,
    FunctionType,
    GlobalDecl,
    GlobalKind,
    LinkMode,
    MojoBinaryExpr,
    MojoCallExpr,
    MojoCastExpr,
    MojoConstExpr,
    MojoDecl,
    MojoIntLiteral,
    MojoRefExpr,
    MojoUnaryExpr,
    Param,
    ParametricBase,
    ParametricType,
    StoredMember,
    StructDecl,
    StructKind,
    StructTraits,
)


class UnitLoweringError(ValueError):
    """Raised when a CIR declaration cannot be lowered to MojoIR."""


def _link_mode_for_options(options: MojoEmitOptions) -> LinkMode:
    if options.linking == "owned_dl_handle":
        return LinkMode.OWNED_DL_HANDLE
    return LinkMode.EXTERNAL_CALL


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
        lowered_type = exact_width_stdint_alias_type(decl.name)
        if lowered_type is None:
            lowered_type = self.session.type_lowerer.run(decl.aliased)
        if isinstance(lowered_type, FunctionType):
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

    def _lower_enum(self, decl: Enum) -> StructDecl:
        underlying = self.session.type_lowerer.run(decl.underlying)
        return StructDecl(
            name=mojo_ident(decl.name),
            traits=[
                StructTraits.COPYABLE,
                StructTraits.MOVABLE,
                StructTraits.REGISTER_PASSABLE,
            ],
            fieldwise_init=True,
            kind=StructKind.ENUM,
            members=[
                StoredMember(
                    index=0,
                    name="value",
                    type=underlying,
                    byte_offset=0,
                )
            ],
            comptime_members=[
                ComptimeMember(
                    name=mojo_ident(member.name),
                    const_value=MojoCallExpr(
                        callee=MojoRefExpr("Self"),
                        args=[
                            MojoCastExpr(
                                target=underlying,
                                expr=MojoIntLiteral(member.value),
                            )
                        ],
                    ),
                )
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
        return lower_struct(decl, context=self.session.struct_context)

    def _typed_const_value(self, value: MojoConstExpr, decl_type) -> MojoConstExpr:
        lowered_type = self.session.type_lowerer.run(decl_type)
        if isinstance(lowered_type, BuiltinType) and lowered_type.name in _MOJO_INT_TYPES:
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
