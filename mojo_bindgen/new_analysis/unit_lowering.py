"""High-level lowering entrypoint from CIR ``Unit`` to MojoIR ``MojoModule``.

This module is intentionally thin. It mirrors the parser's orchestration shape:
one pass owns the overall walk over top-level declarations and delegates
declaration-family lowering to narrower helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.analysis.layout import build_register_passable_map, struct_by_decl_id
from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.ir import (
    Const,
    Decl,
    Enum,
    Function,
    GlobalVar,
    MacroDecl,
    Struct,
    Typedef,
    Unit,
)
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    CallTarget,
    EnumDecl,
    EnumMember,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    GlobalKind,
    LinkMode,
    LoweringNote,
    LoweringSeverity,
    MojoDecl,
    MojoModule,
    Param,
)
from mojo_bindgen.new_analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
)
from mojo_bindgen.new_analysis.struct_lowering import LowerStructPass, StructLoweringContext
from mojo_bindgen.new_analysis.type_lowering import LowerTypePass
from mojo_bindgen.new_analysis.union_lowering import LowerUnionPass


class UnitLoweringError(ValueError):
    """Raised when a CIR declaration cannot be lowered to MojoIR."""


@dataclass(frozen=True)
class LoweringSession:
    """Immutable collaborators shared across one ``Unit`` lowering run."""

    unit: Unit
    type_lowerer: LowerTypePass
    const_lowerer: LowerConstExprPass
    struct_context: StructLoweringContext


def _stub_note(message: str) -> LoweringNote:
    return LoweringNote(
        severity=LoweringSeverity.NOTE,
        message=message,
        category="stub_lowering",
    )


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

    def _lower_typedef(self, decl: Typedef) -> AliasDecl:
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.TYPE_ALIAS,
            type_value=self.session.type_lowerer.run(decl.aliased),
        )

    def _lower_enum(self, decl: Enum) -> EnumDecl:
        return EnumDecl(
            name=mojo_ident(decl.name),
            underlying_type=self.session.type_lowerer.run(decl.underlying),
            align_decorator=None,
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
            call_target=CallTarget(link_mode=LinkMode.EXTERNAL_CALL, symbol=decl.link_name),
        )

    def _lower_global(self, decl: GlobalVar) -> GlobalDecl:
        return GlobalDecl(
            name=mojo_ident(decl.name),
            link_name=decl.link_name,
            value_type=self.session.type_lowerer.run(decl.type),
            is_const=decl.is_const,
            kind=GlobalKind.WRAPPER,
        )

    def _lower_const(self, decl: Const) -> AliasDecl:
        try:
            value = self.session.const_lowerer.run(decl.expr)
        except ConstExprLoweringError:
            return AliasDecl(
                name=mojo_ident(decl.name),
                kind=AliasKind.CONST_VALUE,
                diagnostics=[
                    _stub_note(
                        "constant expression could not be lowered; placeholder alias emitted"
                    )
                ],
            )
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.CONST_VALUE,
            const_value=value,
        )

    def _lower_macro(self, decl: MacroDecl) -> AliasDecl:
        if decl.expr is not None and decl.type is not None:
            try:
                value = self.session.const_lowerer.run(decl.expr)
            except ConstExprLoweringError:
                value = None
            else:
                return AliasDecl(
                    name=mojo_ident(decl.name),
                    kind=AliasKind.MACRO_VALUE,
                    const_value=value,
                )
        return AliasDecl(
            name=mojo_ident(decl.name),
            kind=AliasKind.MACRO_VALUE,
            diagnostics=[_stub_note("macro lowering is incomplete; placeholder alias emitted")],
        )

    def _lower_struct(self, decl: Struct) -> MojoDecl:
        if decl.is_union:
            return self._union_lowerer.run(decl)
        return self._struct_lowerer.run(decl, context=self.session.struct_context)


class LowerUnitPass:
    """Lower an already-normalized CIR ``Unit`` into a MojoIR ``MojoModule``."""

    def run(self, unit: Unit) -> MojoModule:
        type_lowerer = LowerTypePass()
        struct_map = struct_by_decl_id(unit)
        session = LoweringSession(
            unit=unit,
            type_lowerer=type_lowerer,
            const_lowerer=LowerConstExprPass(type_lowering=type_lowerer),
            struct_context=StructLoweringContext(
                struct_map=struct_map,
                register_passable_by_decl_id=build_register_passable_map(struct_map),
                target_abi=unit.target_abi,
                type_lowerer=type_lowerer,
            ),
        )
        decl_lowerer = UnitDeclLowerer(session)
        lowered_decls: list[MojoDecl] = []
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
            link_mode=LinkMode.EXTERNAL_CALL,
            decls=lowered_decls,
        )


def lower_unit(unit: Unit) -> MojoModule:
    """Lower one CIR ``Unit`` into a standalone ``MojoModule``."""

    return LowerUnitPass().run(unit)


__all__ = [
    "LowerUnitPass",
    "LoweringSession",
    "UnitDeclLowerer",
    "UnitLoweringError",
    "lower_unit",
]
