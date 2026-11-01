"""Active roundtrips for current MojoIR, without legacy wire shims."""

from __future__ import annotations

import pytest

from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    BitfieldField,
    BitfieldGroupMember,
    BuiltinType,
    CallTarget,
    CharLiteral,
    ComptimeMember,
    ConstArg,
    CPointer,
    DTypeArg,
    FlexibleTail,
    FunctionDecl,
    GlobalDecl,
    Initializer,
    InitializerParam,
    IntLiteral,
    LinkMode,
    MappingNote,
    MappingSeverity,
    ModuleDependencies,
    ModuleImport,
    MojoArray,
    MojoBinaryExpr,
    MojoBuiltin,
    MojoCallExpr,
    MojoCastExpr,
    MojoFloatLiteral,
    MojoFunctionPtr,
    MojoModule,
    MojoParam,
    MojoPointer,
    MojoRefExpr,
    MojoSizeOfExpr,
    MojoUnaryExpr,
    NameArg,
    NamedType,
    OpaqueStorageMember,
    PaddingMember,
    ParametricBase,
    ParametricType,
    PointerMutability,
    PointerOrigin,
    StoredMember,
    StringLiteral,
    StructDecl,
    SupportDecl,
    SupportDeclKind,
    TypeArg,
)
from mojo_bindgen.serde import (
    decode_c_type,
    decode_mojo_expr,
    decode_mojo_ir,
    decode_mojo_type,
    decode_node,
    dumps_mojo_ir,
    encode_mojo_ir,
    loads_mojo_ir,
    to_debug_dict,
)

I32 = BuiltinType(MojoBuiltin.C_INT)


@pytest.mark.parametrize(
    "value",
    [
        I32,
        NamedType("Record"),
        MojoPointer(None),
        MojoPointer(NamedType("Record"), PointerMutability.IMMUT, PointerOrigin.ANY, True),
        MojoArray(I32, 0),
        MojoArray(MojoPointer(I32), 4),
        MojoFunctionPtr(I32, (MojoParam("x", I32),), "C", True, False),
        ParametricType(ParametricBase.SIMD, (DTypeArg("DType.int32"), ConstArg(4))),
        ParametricType(ParametricBase.UNSAFE_UNION, (TypeArg(I32), NameArg("Record"))),
    ],
)
def test_mojo_type_roundtrip(value) -> None:
    assert decode_mojo_type(to_debug_dict(value)) == value


@pytest.mark.parametrize(
    "value",
    [
        IntLiteral(2),
        MojoFloatLiteral(16.0),
        StringLiteral("λ"),
        CharLiteral("x"),
        MojoRefExpr("name_"),
        MojoUnaryExpr("-", IntLiteral(1)),
        MojoBinaryExpr("+", IntLiteral(1), IntLiteral(2)),
        MojoCastExpr(I32, IntLiteral(2)),
        MojoSizeOfExpr(I32),
        MojoCallExpr(MojoRefExpr("E"), (IntLiteral(2),)),
    ],
)
def test_mojo_expression_roundtrip(value) -> None:
    assert decode_mojo_expr(to_debug_dict(value)) == value


def test_module_roundtrip_preserves_all_target_declarations_and_member_shapes() -> None:
    note = MappingNote(MappingSeverity.WARNING, "note", "test")
    record = StructDecl(
        "Record",
        members=(
            StoredMember(0, "x", I32, 0),
            PaddingMember("padding", 4, 4),
            OpaqueStorageMember("storage", 8),
            BitfieldGroupMember(
                "bits", I32, 8, 1, 32, (BitfieldField(1, "flag", I32, 0, 1, False),)
            ),
        ),
        comptime_members=(ComptimeMember("N", const_value=IntLiteral(2)),),
        initializers=(Initializer((InitializerParam("x", I32),)),),
        flexible_tail=FlexibleTail("tail", I32, "c99_empty", 12),
        diagnostics=(note,),
    )
    module = MojoModule(
        "input.h",
        "lib",
        "lib",
        LinkMode.EXTERNAL_CALL,
        dependencies=ModuleDependencies(
            (ModuleImport("std.ffi", ("c_int",)),),
            (SupportDecl(SupportDeclKind.GLOBAL_SYMBOL_HELPERS),),
        ),
        decls=(
            record,
            AliasDecl("T", AliasKind.TYPE_ALIAS, type_value=I32),
            FunctionDecl(
                "f",
                "f",
                (MojoParam("x", I32),),
                I32,
                call_target=CallTarget(LinkMode.EXTERNAL_CALL, "f"),
            ),
            GlobalDecl("g", "g", I32),
        ),
    )
    assert loads_mojo_ir(dumps_mojo_ir(module)) == module
    assert decode_mojo_ir(encode_mojo_ir(module)) == module
    assert isinstance(decode_mojo_ir(encode_mojo_ir(module)).decls, tuple)


def test_kind_field_is_data_not_a_serialization_override() -> None:
    alias = AliasDecl("T", AliasKind.TYPE_ALIAS, type_value=I32)
    raw = to_debug_dict(alias)
    assert raw["kind"] == "AliasDecl"
    assert raw["fields"]["kind"] == "type_alias"
    assert raw["fields"]["diagnostics"] == []
    assert raw["fields"]["const_value"] is None
    assert decode_node(raw, AliasDecl) == alias


def test_wrong_stage_and_malformed_records_are_rejected() -> None:
    with pytest.raises(ValueError):
        decode_c_type(to_debug_dict(MojoPointer(None)))
    with pytest.raises(ValueError):
        decode_mojo_type(to_debug_dict(CPointer(None)))
    with pytest.raises(ValueError):
        decode_mojo_expr({"kind": "CFloatLiteral", "fields": {"spelling": "1.0"}})
    raw = to_debug_dict(MojoArray(I32, 2))
    raw["fields"]["element"] = to_debug_dict(CPointer(None))
    with pytest.raises(ValueError):
        decode_mojo_type(raw)
    with pytest.raises(ValueError):
        decode_mojo_type({"kind": "MojoArray", "fields": {"element": to_debug_dict(I32)}})
    raw = to_debug_dict(I32)
    raw["fields"]["unexpected"] = 1
    with pytest.raises(ValueError):
        decode_mojo_type(raw)
