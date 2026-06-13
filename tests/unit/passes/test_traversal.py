from __future__ import annotations

from mojo_bindgen.analysis.traversal import (
    decl_id,
    iter_const_expr_refs,
    iter_const_expr_types,
    iter_decl_referenced_types,
    iter_unit_typerefs,
)
from mojo_bindgen.ir import (
    BinaryExpr,
    ByteOrder,
    CastExpr,
    Const,
    Function,
    IntKind,
    IntLiteral,
    IntType,
    Param,
    RefExpr,
    SizeOfExpr,
    TargetABI,
    TypeRef,
    Unit,
    VoidType,
)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _unit(*decls) -> Unit:
    return Unit(
        source_header="input.h",
        library="test",
        link_name="test",
        target_abi=TargetABI(
            pointer_size_bytes=8,
            pointer_align_bytes=8,
            byte_order=ByteOrder.LITTLE,
        ),
        decls=list(decls),
    )


def test_decl_id_uses_decl_ids_for_declarations_and_names_for_constants() -> None:
    fn = Function(
        decl_id="function:f",
        name="f",
        link_name="f",
        ret=VoidType(),
        params=[],
    )
    const = Const(name="SIZE", type=_i32(), expr=IntLiteral(1))

    assert decl_id(fn) == "function:f"
    assert decl_id(const) == "SIZE"


def test_const_expr_traversal_yields_types_and_symbol_refs() -> None:
    expr = BinaryExpr(
        op="+",
        lhs=CastExpr(target=_i32(), expr=RefExpr("BASE")),
        rhs=SizeOfExpr(target=TypeRef("typedef:Alias", "Alias", _i32())),
    )

    assert tuple(type(t).__name__ for t in iter_const_expr_types(expr)) == (
        "IntType",
        "TypeRef",
    )
    assert tuple(ref.name for ref in iter_const_expr_refs(expr)) == ("BASE",)


def test_decl_referenced_types_include_signature_and_const_expr_type_slots() -> None:
    alias = TypeRef("typedef:Alias", "Alias", _i32())
    const = Const(
        name="SIZE",
        type=alias,
        expr=SizeOfExpr(target=alias),
    )

    assert tuple(type(t).__name__ for t in iter_decl_referenced_types(const)) == (
        "TypeRef",
        "TypeRef",
    )


def test_iter_unit_typerefs_finds_type_refs_inside_const_expressions() -> None:
    alias = TypeRef("typedef:Alias", "Alias", _i32())
    fn = Function(
        decl_id="function:f",
        name="f",
        link_name="f",
        ret=VoidType(),
        params=[Param(name="x", type=alias)],
    )
    const = Const(name="SIZE", type=_i32(), expr=SizeOfExpr(target=alias))

    assert tuple(ref.decl_id for ref in iter_unit_typerefs(_unit(fn, const))) == (
        "typedef:Alias",
        "typedef:Alias",
    )
