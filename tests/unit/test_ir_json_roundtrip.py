"""Current CIR debug records preserve typed recursive values and immutable children."""

from __future__ import annotations

import pytest

from mojo_bindgen.ir import (
    AtomicType,
    ByteOrder,
    CArray,
    CBinaryExpr,
    CCallExpr,
    CCastExpr,
    CFloatLiteral,
    CFunctionPtr,
    CharLiteral,
    CNullPtrLiteral,
    ComplexType,
    Const,
    CParam,
    CPointer,
    CRefExpr,
    CSizeOfExpr,
    CUnaryExpr,
    DocComment,
    Enum,
    Enumerant,
    EnumRef,
    Field,
    FloatKind,
    FloatType,
    Function,
    GlobalVar,
    IntKind,
    IntLiteral,
    IntType,
    IRDiagnostic,
    MacroDecl,
    OpaqueRecordRef,
    QualifiedType,
    Qualifiers,
    StringLiteral,
    Struct,
    StructRef,
    TargetABI,
    Typedef,
    TypeRef,
    Unit,
    UnsupportedType,
    VectorType,
    VoidType,
)
from mojo_bindgen.serde import (
    decode_c_expr,
    decode_c_type,
    decode_cir,
    dumps_cir,
    encode_cir,
    loads_cir,
    to_debug_dict,
)

I32 = IntType(IntKind.INT, 4, 4)
F32 = FloatType(FloatKind.FLOAT, 4, 4)


@pytest.mark.parametrize(
    "value",
    [
        VoidType(),
        *[IntType(kind, 4, 4) for kind in IntKind],
        *[FloatType(kind, 8, 8) for kind in FloatKind],
        QualifiedType(I32, Qualifiers(True, True, True)),
        AtomicType(I32, 4, 4),
        CPointer(None, 8, 8),
        CPointer(CArray(I32, 3), 8, 8),
        *[
            CArray(I32, None if shape != "fixed" else 3, shape)
            for shape in ("fixed", "incomplete", "flexible", "variable")
        ],
        CFunctionPtr(CPointer(None), (CParam("x", I32),), ("x",), True, "c", True, 8, 8),
        OpaqueRecordRef("opaque:F", "F", "F"),
        UnsupportedType("unknown", "x", "unmodeled", 4, 4),
        ComplexType(F32, 8, 4),
        VectorType(I32, 4, 16),
        StructRef("struct:S", "S", "S"),
        EnumRef("enum:E", "E", "E", I32),
        TypeRef("typedef:T", "T", CPointer(I32)),
    ],
)
def test_c_type_roundtrip(value) -> None:
    assert decode_c_type(to_debug_dict(value)) == value


@pytest.mark.parametrize(
    "value",
    [
        IntLiteral(2),
        CFloatLiteral("0x1.0p4F"),
        StringLiteral('λ\\"'),
        CharLiteral("x"),
        CNullPtrLiteral(),
        CRefExpr("naïve"),
        CUnaryExpr("-", IntLiteral(3)),
        CBinaryExpr("+", IntLiteral(1), IntLiteral(2)),
        CCastExpr(I32, IntLiteral(7)),
        CSizeOfExpr(CArray(I32, 4)),
        CCallExpr(CRefExpr("F"), (IntLiteral(2),)),
    ],
)
def test_c_expression_roundtrip(value) -> None:
    assert decode_c_expr(to_debug_dict(value)) == value


def test_unit_roundtrip_preserves_every_declaration_family() -> None:
    doc = DocComment("Record documentation")
    unit = Unit(
        "input.h",
        "lib",
        "lib",
        TargetABI(8, 8, ByteOrder.LITTLE),
        (
            Struct(
                "struct:S",
                "S",
                "S",
                (Field("next", "next", CPointer(StructRef("struct:S", "S", "S")), 0),),
                8,
                8,
                doc=doc,
            ),
            Function("f", "f", I32, (CParam("a", CPointer(I32)),), decl_id="fn:f"),
            Typedef("typedef:T", "T", I32, I32),
            Enum("enum:E", "E", "E", I32, (Enumerant("A", "A", 1),)),
            Const("N", I32, IntLiteral(2)),
            GlobalVar("var:g", "g", "g", I32, initializer=IntLiteral(1)),
            MacroDecl("F", ("1",), "object_like_supported", IntLiteral(1), I32),
        ),
        (IRDiagnostic("warning", "note"),),
    )
    restored = loads_cir(dumps_cir(unit))
    assert restored == unit
    assert isinstance(restored.decls, tuple)
    assert isinstance(restored.decls[0], Struct)
    assert isinstance(restored.decls[0].fields, tuple)
    assert decode_cir(encode_cir(unit)) == unit


def test_debug_encoding_keeps_all_fields_and_constructor_defaults() -> None:
    raw = to_debug_dict(AtomicType(I32))
    assert raw["fields"]["size_bytes"] is None
    del raw["fields"]["size_bytes"]
    assert decode_c_type(raw) == AtomicType(I32)
    with pytest.raises(ValueError):
        decode_c_type({"kind": "NoSuchType", "fields": {}})
