from __future__ import annotations

from dataclasses import dataclass
from typing import assert_never

from mojo_bindgen.analysis.calling_convention import require_c_calling_convention
from mojo_bindgen.analysis.common import mojo_ident
from mojo_bindgen.analysis.facts.c_abi import CABIQueries
from mojo_bindgen.analysis.facts.context import AnalysisContext
from mojo_bindgen.analysis.facts.parameter_types import parameter_type
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
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass, TypeMappingError
from mojo_bindgen.analysis.mojo.union_mapping import MapUnionPass
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    AtomicType,
    CallTarget,
    Const,
    CType,
    Decl,
    Enum,
    Function,
    FunctionAttrs,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    GlobalKind,
    GlobalVar,
    InlineDisposition,
    IntLiteral,
    LinkMode,
    MacroDecl,
    MojoCallExpr,
    MojoCastExpr,
    MojoConstExpr,
    MojoDecl,
    MojoParam,
    MojoRefExpr,
    NamedType,
    QualifiedType,
    Struct,
    Typedef,
    TypeRef,
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
    context: AnalysisContext


class UnitDeclMapper:
    """Map one top-level CIR declaration into one or more MojoIR declarations."""

    def __init__(self, session: MappingSession) -> None:
        self.session = session
        self._emitted_const_names: set[str] = set()
        self._c_abi = CABIQueries(session.context)
        self._union_mapper = MapUnionPass(type_mapper=session.type_mapper, context=session.context)
        self._macro_mapper = MacroMapper(
            const_expr_mapper=session.const_expr_mapper,
            type_mapper=session.type_mapper,
            emitted_const_names=self._emitted_const_names,
        )

    def map_decl(self, decl: Decl) -> tuple[MojoDecl, ...]:
        match decl:
            case Typedef():
                alias = self._map_typedef(decl)
                return () if alias is None else (alias,)
            case Enum():
                return tuple(self._map_enum(decl))
            case Function():
                return (self._map_function(decl),)
            case GlobalVar():
                return (self._map_global(decl),)
            case Const():
                return (self._map_const(decl),)
            case MacroDecl():
                macro = self._macro_mapper.map(decl)
                return () if macro is None else (macro,)
            case Struct():
                return (self._map_struct(decl),)
        assert_never(decl)

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
                const_value=MojoCallExpr(
                    callee=MojoRefExpr(enum_name),
                    args=(MojoCastExpr(target=underlying, expr=IntLiteral(member.value)),),
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
        require_c_calling_convention(decl.calling_convention)
        kind = FunctionKind.WRAPPER
        diagnostics = []
        if decl.attrs.inline_disposition != InlineDisposition.NONE:
            kind = FunctionKind.DIRECTIVE_STUB
            diagnostics.append(
                stub_note(
                    "inline declaration may not provide a stable external symbol; wrapper omitted"
                )
            )
        elif decl.is_variadic and self.session.options.linking == "owned_dl_handle":
            kind = FunctionKind.VARIADIC_STUB
            diagnostics.append(stub_note("OwnedDLHandle does not expose variadic C ABI metadata"))
        elif (
            not decl.is_variadic
            and self.session.options.linking == "external_call"
            and self._c_abi.memory_return_eligible(decl)
        ):
            kind = FunctionKind.EXTERN_DECLARATION
        if kind in (FunctionKind.WRAPPER, FunctionKind.EXTERN_DECLARATION):
            reason = self._c_abi.signature_reason(decl)
            if reason:
                kind = FunctionKind.ABI_STUB
                diagnostics.append(stub_note(reason + "; callable binding omitted"))
        return FunctionDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            params=tuple(
                (
                    MojoParam(
                        name=mojo_ident(param.name, fallback=f"a{i}") if param.name else f"a{i}",
                        type=self.session.type_mapper.run(
                            parameter_type(param.type, self.session.unit.target_abi)
                        ),
                        doc=param.doc,
                    )
                    for i, param in enumerate(decl.params)
                )
            ),
            return_type=self.session.type_mapper.run(decl.ret),
            kind=kind,
            call_target=CallTarget(
                link_mode=_link_mode_for_options(self.session.options),
                symbol=decl.link_name,
            ),
            attrs=FunctionAttrs(
                inline_disposition=decl.attrs.inline_disposition,
                is_noreturn=decl.attrs.is_noreturn,
            ),
            num_fixed_args=len(decl.params) if decl.is_variadic else None,
            diagnostics=tuple(diagnostics),
            doc=decl.doc,
        )

    def _map_global(self, decl: GlobalVar) -> GlobalDecl:
        mapped_type = self.session.type_mapper.run(decl.type)
        source_type = decl.type
        while isinstance(source_type, (QualifiedType, TypeRef)):
            source_type = (
                source_type.unqualified
                if isinstance(source_type, QualifiedType)
                else source_type.canonical
            )
        is_atomic = isinstance(source_type, AtomicType)
        value_supported = self.session.type_mapper.value_supported(decl.type)
        return GlobalDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            value_type=mapped_type,
            is_const=decl.is_const,
            kind=(GlobalKind.STUB if is_atomic or not value_supported else GlobalKind.WRAPPER),
            diagnostics=(
                (
                    stub_note(
                        "global has no supported Mojo value representation; manual binding required"
                    ),
                )
                if not value_supported
                else ()
            ),
            doc=decl.doc,
        )

    def _map_const(self, decl: Const) -> AliasDecl:
        try:
            value = self.session.const_expr_mapper.run(decl.expr)
            typed_value = self._typed_const_value(value, decl.type)
        except (ConstExprMappingError, TypeMappingError):
            return AliasDecl(
                name=mojo_ident(decl.name),
                kind=AliasKind.CONST_VALUE,
                diagnostics=(
                    stub_note("constant expression could not be mapped; placeholder alias emitted"),
                ),
                doc=decl.doc,
            )
        name = mojo_ident(decl.name)
        self._emitted_const_names.add(name)
        return AliasDecl(
            name=name,
            kind=AliasKind.CONST_VALUE,
            const_value=typed_value,
            doc=decl.doc,
        )

    def _map_struct(self, decl: Struct) -> MojoDecl:
        if decl.is_union:
            return self._union_mapper.run(decl)
        return map_struct(decl, context=self.session.struct_context)

    def _typed_const_value(self, value: MojoConstExpr, decl_type: CType) -> MojoConstExpr:
        return typed_const_value(value, decl_type, type_mapper=self.session.type_mapper)
