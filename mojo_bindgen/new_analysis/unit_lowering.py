"""High-level lowering entrypoint from CIR ``Unit`` to MojoIR ``MojoModule``.

This module is intentionally thin. It mirrors the parser's orchestration shape:
one pass owns the overall walk over top-level declarations and delegates
declaration-family lowering to narrower helpers.
"""

from __future__ import annotations

from dataclasses import dataclass

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
    StructDecl,
    StructKind,
)
from mojo_bindgen.new_analysis.const_lowering import (
    ConstExprLoweringError,
    LowerConstExprPass,
)
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


def _stub_note(message: str) -> LoweringNote:
    return LoweringNote(
        severity=LoweringSeverity.NOTE,
        message=message,
        category="stub_lowering",
    )


def _record_name(decl: Struct) -> str:
    raw_name = decl.name.strip() or decl.c_name.strip()
    fallback = "anonymous_union" if decl.is_union else "anonymous_struct"
    return mojo_ident(raw_name, fallback=fallback)


class _StubStructLowerer:
    """Temporary struct lowering until record-layout lowering is implemented."""

    def lower(self, decl: Struct) -> StructDecl:
        if decl.is_complete:
            kind = StructKind.PLAIN
            align = decl.align_bytes
            note = _stub_note("struct member lowering not implemented yet")
        else:
            kind = StructKind.OPAQUE
            align = None
            note = _stub_note(
                "opaque struct placeholder emitted; member lowering not implemented yet"
            )
        return StructDecl(
            name=_record_name(decl),
            kind=kind,
            traits=[],
            align=align,
            align_decorator=None,
            fieldwise_init=False,
            members=[],
            initializers=[],
            diagnostics=[note],
        )


class UnitDeclLowerer:
    """Lower one top-level CIR declaration into one or more MojoIR declarations."""

    def __init__(self, session: LoweringSession) -> None:
        self.session = session
        self._struct_lowerer = _StubStructLowerer()
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
        return self._struct_lowerer.lower(decl)


class LowerUnitPass:
    """Lower an already-normalized CIR ``Unit`` into a MojoIR ``MojoModule``."""

    def run(self, unit: Unit) -> MojoModule:
        type_lowerer = LowerTypePass()
        session = LoweringSession(
            unit=unit,
            type_lowerer=type_lowerer,
            const_lowerer=LowerConstExprPass(type_lowering=type_lowerer),
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
