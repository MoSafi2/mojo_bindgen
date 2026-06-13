from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.alias_lowering import lower_typedef_alias
from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
)
from mojo_bindgen.analysis.const_value_lowering import typed_const_value
from mojo_bindgen.analysis.lowering_support import stub_note
from mojo_bindgen.analysis.macro_lowering import MacroLowerer
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.struct_lowering import (
    StructLoweringContext,
    lower_struct,
)
from mojo_bindgen.analysis.type_lowering import LowerTypePass
from mojo_bindgen.analysis.union_lowering import LowerUnionPass
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    CallExpr,
    CallTarget,
    CastExpr,
    Const,
    ConstExpr,
    Decl,
    Enum,
    Function,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    GlobalKind,
    GlobalVar,
    IntLiteral,
    LinkMode,
    MacroDecl,
    MojoDecl,
    NamedType,
    Param,
    ParametricBase,
    ParametricType,
    RefExpr,
    Struct,
    Typedef,
    Unit,
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
        self._emitted_const_names: set[str] = set()
        self._union_lowerer = LowerUnionPass(type_lowerer=session.type_lowerer)
        self._macro_lowerer = MacroLowerer(
            const_lowerer=session.const_lowerer,
            type_lowerer=session.type_lowerer,
            emitted_const_names=self._emitted_const_names,
        )

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
        return lower_typedef_alias(
            c_name=decl.name,
            aliased=decl.aliased,
            type_lowerer=self.session.type_lowerer,
            doc=decl.doc,
        )

    def _lower_enum(self, decl: Enum) -> list[MojoDecl]:
        underlying = self.session.type_lowerer.run(decl.underlying)
        enum_name = mojo_ident(decl.name)
        enum_decl = AliasDecl(
            name=enum_name,
            kind=AliasKind.TYPE_ALIAS,
            type_value=underlying,
            doc=decl.doc,
        )
        aliases = [
            AliasDecl(
                name=mojo_ident(alias_name),
                kind=AliasKind.TYPE_ALIAS,
                type_value=NamedType(enum_name),
            )
            for alias_name in decl.alias_names
        ]
        enumerants = [
            AliasDecl(
                name=mojo_ident(member.name),
                kind=AliasKind.CONST_VALUE,
                const_type=NamedType(enum_name),
                const_value=CallExpr(
                    callee=RefExpr(enum_name),
                    args=[
                        CastExpr(
                            target=underlying,
                            expr=IntLiteral(member.value),
                        )
                    ],
                ),
                doc=member.doc,
            )
            for member in decl.enumerants
        ]
        self._emitted_const_names.add(enum_name)
        self._emitted_const_names.update(mojo_ident(member.name) for member in decl.enumerants)
        self._emitted_const_names.update(mojo_ident(alias_name) for alias_name in decl.alias_names)
        return [enum_decl, *aliases, *enumerants]

    def _lower_function(self, decl: Function) -> FunctionDecl:
        return FunctionDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            params=[
                Param(
                    name=(mojo_ident(param.name, fallback=f"a{i}") if param.name else f"a{i}"),
                    type=self.session.type_lowerer.run(param.type),
                    doc=param.doc,
                )
                for i, param in enumerate(decl.params)
            ],
            return_type=self.session.type_lowerer.run(decl.ret),
            kind=(FunctionKind.VARIADIC_STUB if decl.is_variadic else FunctionKind.WRAPPER),
            call_target=CallTarget(
                link_mode=_link_mode_for_options(self.session.options),
                symbol=decl.link_name,
            ),
            doc=decl.doc,
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
            doc=decl.doc,
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
                doc=decl.doc,
            )
        name = mojo_ident(decl.name)
        self._emitted_const_names.add(name)
        return AliasDecl(
            name=name,
            kind=AliasKind.CONST_VALUE,
            const_value=self._typed_const_value(value, decl.type),
            doc=decl.doc,
        )

    def _lower_macro(self, decl: MacroDecl) -> AliasDecl | None:
        return self._macro_lowerer.lower(decl)

    def _lower_struct(self, decl: Struct) -> MojoDecl:
        if decl.is_union:
            return self._union_lowerer.run(decl)
        return lower_struct(decl, context=self.session.struct_context)

    def _typed_const_value(self, value: ConstExpr, decl_type) -> ConstExpr:
        return typed_const_value(value, decl_type, type_lowerer=self.session.type_lowerer)
