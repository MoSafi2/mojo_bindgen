"""Tests for CIR declaration canonicalization."""

from __future__ import annotations

from mojo_bindgen.analysis.cir_canonicalizer import CIRCanonicalizer
from mojo_bindgen.ir import (
    ByteOrder,
    Const,
    Function,
    IntKind,
    IntLiteral,
    IntType,
    MacroDecl,
    Param,
    RefExpr,
    TargetABI,
    Unit,
    VoidType,
)


def _abi() -> TargetABI:
    return TargetABI(
        pointer_size_bytes=8,
        pointer_align_bytes=8,
        byte_order=ByteOrder.LITTLE,
    )


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _unit(decls) -> Unit:
    return Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=list(decls),
    )


def test_canonicalizer_dedupes_macros_last_definition_wins() -> None:
    unit = _unit(
        [
            MacroDecl(
                name="VALUE",
                tokens=["1"],
                kind="object_like_supported",
                expr=IntLiteral(1),
                type=_i32(),
            ),
            MacroDecl(
                name="VALUE",
                tokens=["2"],
                kind="object_like_supported",
                expr=IntLiteral(2),
                type=_i32(),
            ),
        ]
    )

    out = CIRCanonicalizer().canonicalize(unit)

    assert len(out.decls) == 1
    macro = out.decls[0]
    assert isinstance(macro, MacroDecl)
    assert macro.tokens == ["2"]
    assert isinstance(macro.expr, IntLiteral)
    assert macro.expr.value == 2


def test_canonicalizer_dedupes_identical_functions_only() -> None:
    original = Function(
        decl_id="f:1",
        name="read_value",
        link_name="read_value",
        ret=_i32(),
        params=[Param(name="value", type=_i32())],
    )
    duplicate = Function(
        decl_id="f:2",
        name="read_value",
        link_name="read_value",
        ret=_i32(),
        params=[Param(name="renamed", type=_i32())],
    )
    conflict = Function(
        decl_id="f:3",
        name="read_value",
        link_name="read_value",
        ret=VoidType(),
        params=[Param(name="value", type=_i32())],
    )
    unit = _unit([original, duplicate, conflict])

    out = CIRCanonicalizer().canonicalize(unit)

    functions = [decl for decl in out.decls if isinstance(decl, Function)]
    assert [fn.decl_id for fn in functions] == ["f:1", "f:3"]


def test_canonicalizer_drops_self_alias_macro_when_const_claims_name() -> None:
    unit = _unit(
        [
            Const(name="_PC_LINK_MAX", type=_i32(), expr=IntLiteral(0)),
            MacroDecl(
                name="_PC_LINK_MAX",
                tokens=["_PC_LINK_MAX"],
                kind="object_like_supported",
                expr=RefExpr("_PC_LINK_MAX"),
                type=_i32(),
            ),
        ]
    )

    out = CIRCanonicalizer().canonicalize(unit)

    assert [type(decl).__name__ for decl in out.decls] == ["Const"]
