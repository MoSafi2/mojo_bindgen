from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.mojo.alias_mapping import map_typedef_alias
from mojo_bindgen.analysis.mojo.const_expr_mapping import (
    ConstExprMappingError,
    MapConstExprPass,
)
from mojo_bindgen.analysis.mojo.const_value_mapping import typed_const_value
from mojo_bindgen.analysis.mojo.macro_mapping import MacroMapper
from mojo_bindgen.analysis.mojo.mapping_support import stub_note
from mojo_bindgen.analysis.mojo.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.mojo.struct_mapping import (
    StructMappingContext,
    map_struct,
)
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.mojo.union_mapping import MapUnionPass
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


class UnitMappingError(ValueError):
    """Raised when a CIR declaration cannot be mapped to MojoIR."""


def _link_mode_for_options(options: MojoEmitOptions) -> LinkMode:
    if options.linking == "owned_dl_handle":
        return LinkMode.OWNED_DL_HANDLE
    return LinkMode.EXTERNAL_CALL


@dataclass(frozen=True)
class MappingSession:
    """Immutable collaborators shared across one ``Unit`` mapping run."""

    unit: Unit
    options: MojoEmitOptions
    type_mapper: MapTypePass
    const_expr_mapper: MapConstExprPass
    struct_context: StructMappingContext


class UnitDeclMapper:
    """Map one top-level CIR declaration into one or more MojoIR declarations."""

    def __init__(self, session: MappingSession) -> None:
        self.session = session
        self._emitted_const_names: set[str] = set()
        self._union_mapper = MapUnionPass(type_mapper=session.type_mapper)
        self._macro_mapper = MacroMapper(
            const_expr_mapper=session.const_expr_mapper,
            type_mapper=session.type_mapper,
            emitted_const_names=self._emitted_const_names,
        )

    def map_decl(self, decl: Decl) -> MojoDecl | list[MojoDecl] | None:
        if isinstance(decl, Typedef):
            return self._map_typedef(decl)
        if isinstance(decl, Enum):
            return self._map_enum(decl)
        if isinstance(decl, Function):
            return self._map_function(decl)
        if isinstance(decl, GlobalVar):
            return self._map_global(decl)
        if isinstance(decl, Const):
            return self._map_const(decl)
        if isinstance(decl, MacroDecl):
            return self._map_macro(decl)
        if isinstance(decl, Struct):
            return self._map_struct(decl)
        raise UnitMappingError(f"unsupported CIR declaration node: {type(decl).__name__!r}")

    def _map_typedef(self, decl: Typedef) -> AliasDecl | None:
        return map_typedef_alias(
            c_name=decl.name,
            aliased=decl.aliased,
            type_mapper=self.session.type_mapper,
            doc=decl.doc,
        )

    def _map_enum(self, decl: Enum) -> list[MojoDecl]:
        underlying = self.session.type_mapper.run(decl.underlying)
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

    def _map_function(self, decl: Function) -> FunctionDecl:
        return FunctionDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            params=[
                Param(
                    name=(mojo_ident(param.name, fallback=f"a{i}") if param.name else f"a{i}"),
                    type=self.session.type_mapper.run(param.type),
                    doc=param.doc,
                )
                for i, param in enumerate(decl.params)
            ],
            return_type=self.session.type_mapper.run(decl.ret),
            kind=(FunctionKind.VARIADIC_STUB if decl.is_variadic else FunctionKind.WRAPPER),
            call_target=CallTarget(
                link_mode=_link_mode_for_options(self.session.options),
                symbol=decl.link_name,
            ),
            doc=decl.doc,
        )

    def _map_global(self, decl: GlobalVar) -> GlobalDecl:
        mapped_type = self.session.type_mapper.run(decl.type)
        is_atomic = (
            isinstance(mapped_type, ParametricType) and mapped_type.base == ParametricBase.ATOMIC
        )
        return GlobalDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            value_type=mapped_type,
            is_const=decl.is_const,
            kind=(GlobalKind.STUB if is_atomic else GlobalKind.WRAPPER),
            doc=decl.doc,
        )

    def _map_const(self, decl: Const) -> AliasDecl:
        try:
            value = self.session.const_expr_mapper.run(decl.expr)
        except ConstExprMappingError:
            return AliasDecl(
                name=mojo_ident(decl.name),
                kind=AliasKind.CONST_VALUE,
                diagnostics=[
                    stub_note("constant expression could not be mapped; placeholder alias emitted")
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

    def _map_macro(self, decl: MacroDecl) -> AliasDecl | None:
        return self._macro_mapper.map(decl)

    def _map_struct(self, decl: Struct) -> MojoDecl:
        if decl.is_union:
            return self._union_mapper.run(decl)
        return map_struct(decl, context=self.session.struct_context)

    def _typed_const_value(self, value: ConstExpr, decl_type) -> ConstExpr:
        return typed_const_value(value, decl_type, type_mapper=self.session.type_mapper)
