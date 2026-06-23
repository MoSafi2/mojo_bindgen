# Smoke test: build, serialize, deserialize, and copy every IR node defined in
# `mojo/ir.mojo`. Run with:
#
#   pixi run mojo -I . -I .pixi/envs/default/lib/mojo tests/mojo/test_ir_serde.mojo

from mojo.ir import (
    serialize, deserialize_ir,
    VoidType, IntType, FloatType, QualifiedType, AtomicType, Pointer, Array,
    FunctionPtr, OpaqueRecordRef, UnsupportedType, ComplexType, VectorType,
    StructRef, EnumRef, TypeRef,
    IntLiteral as IRIntLiteral, FloatLiteral as IRFloatLiteral,
    StringLiteral as IRStringLiteral, CharLiteral as IRCharLiteral,
    NullPtrLiteral, RefExpr, UnaryExpr, BinaryExpr, CastExpr, SizeOfExpr,
    CallExpr, Field, Struct, Enum, Typedef, Function, Const, MacroDecl,
    GlobalVar, Unit, BuiltinType, NamedType, DTypeArg, ConstArg, NameArg,
    TypeArg, ParametricType, StoredMember, PaddingMember, OpaqueStorageMember,
    BitfieldField, BitfieldGroupMember, ComptimeMember, InitializerParam,
    Initializer, FlexibleTail, StructDecl, AliasDecl, CallTarget, FunctionDecl,
    GlobalDecl, MojoModule, Qualifiers, DocComment, TargetABI, IRDiagnostic,
    MappingNote, ModuleImport, SupportDecl, ModuleDependencies, PrimitiveDType,
    Enumerant, Param, IntKind, ByteOrder,
)
from std.testing import assert_equal, assert_true
from emberjson import parse


# Build every IR node, copy it, serialize the copy, and confirm the JSON
# contains the expected `kind` discriminator. This exercises the full set of
# @fieldwise_init structs and the EmberJson reflection serializer.
def _check_kind(kind: String, json: String) raises:
    var v = parse(json)
    assert_true(
        v.is_object(),
        "expected object JSON for " + kind + ", got: " + json,
    )
    assert_equal(v.object()["kind"].string(), kind)


# Nodes that intentionally omit the `kind` discriminator in the JSON wire
# format (matching Python IR's KIND=None): Qualifiers, Enumerant, Param,
# IRDiagnostic. Just verify they round-trip as objects.
def _check_no_kind(json: String) raises:
    var v = parse(json)
    assert_true(v.is_object(), "expected object JSON, got: " + json)


def test_every_node_serializes_with_kind() raises:
    _check_kind("VoidType", serialize(VoidType().copy()))
    _check_kind("IntType", serialize(IntType().copy()))
    _check_kind("FloatType", serialize(FloatType().copy()))
    _check_kind("QualifiedType", serialize(QualifiedType().copy()))
    _check_kind("AtomicType", serialize(AtomicType().copy()))
    _check_kind("Pointer", serialize(Pointer().copy()))
    _check_kind("Array", serialize(Array().copy()))
    _check_kind("FunctionPtr", serialize(FunctionPtr().copy()))
    _check_kind("OpaqueRecordRef", serialize(OpaqueRecordRef().copy()))
    _check_kind("UnsupportedType", serialize(UnsupportedType().copy()))
    _check_kind("ComplexType", serialize(ComplexType().copy()))
    _check_kind("VectorType", serialize(VectorType().copy()))
    _check_kind("StructRef", serialize(StructRef().copy()))
    _check_kind("EnumRef", serialize(EnumRef().copy()))
    _check_kind("TypeRef", serialize(TypeRef().copy()))
    _check_kind("IntLiteral", serialize(IRIntLiteral().copy()))
    _check_kind("FloatLiteral", serialize(IRFloatLiteral().copy()))
    _check_kind("StringLiteral", serialize(IRStringLiteral().copy()))
    _check_kind("CharLiteral", serialize(IRCharLiteral().copy()))
    _check_kind("NullPtrLiteral", serialize(NullPtrLiteral().copy()))
    _check_kind("RefExpr", serialize(RefExpr().copy()))
    _check_kind("UnaryExpr", serialize(UnaryExpr().copy()))
    _check_kind("BinaryExpr", serialize(BinaryExpr().copy()))
    _check_kind("CastExpr", serialize(CastExpr().copy()))
    _check_kind("SizeOfExpr", serialize(SizeOfExpr().copy()))
    _check_kind("CallExpr", serialize(CallExpr().copy()))
    _check_kind("Field", serialize(Field().copy()))
    _check_kind("Struct", serialize(Struct().copy()))
    _check_kind("Enum", serialize(Enum().copy()))
    _check_kind("Typedef", serialize(Typedef().copy()))
    _check_kind("Function", serialize(Function().copy()))
    _check_kind("Const", serialize(Const().copy()))
    _check_kind("MacroDecl", serialize(MacroDecl().copy()))
    _check_kind("GlobalVar", serialize(GlobalVar().copy()))
    _check_kind("Unit", serialize(Unit().copy()))
    _check_kind("BuiltinType", serialize(BuiltinType().copy()))
    _check_kind("NamedType", serialize(NamedType().copy()))
    _check_kind("DTypeArg", serialize(DTypeArg().copy()))
    _check_kind("ConstArg", serialize(ConstArg().copy()))
    _check_kind("NameArg", serialize(NameArg().copy()))
    _check_kind("TypeArg", serialize(TypeArg().copy()))
    _check_kind("ParametricType", serialize(ParametricType().copy()))
    _check_kind("StoredMember", serialize(StoredMember().copy()))
    _check_kind("PaddingMember", serialize(PaddingMember().copy()))
    _check_kind(
        "OpaqueStorageMember", serialize(OpaqueStorageMember().copy())
    )
    _check_kind("BitfieldField", serialize(BitfieldField().copy()))
    _check_kind(
        "BitfieldGroupMember", serialize(BitfieldGroupMember().copy())
    )
    _check_kind("ComptimeMember", serialize(ComptimeMember().copy()))
    _check_kind("InitializerParam", serialize(InitializerParam().copy()))
    _check_kind("Initializer", serialize(Initializer().copy()))
    _check_kind("FlexibleTail", serialize(FlexibleTail().copy()))
    _check_kind("StructDecl", serialize(StructDecl().copy()))
    _check_kind("AliasDecl", serialize(AliasDecl().copy()))
    _check_kind("CallTarget", serialize(CallTarget().copy()))
    _check_kind("FunctionDecl", serialize(FunctionDecl().copy()))
    _check_kind("GlobalDecl", serialize(GlobalDecl().copy()))
    _check_kind("MojoModule", serialize(MojoModule().copy()))
    _check_no_kind(serialize(Qualifiers().copy()))
    _check_kind("DocComment", serialize(DocComment().copy()))
    _check_kind("TargetABI", serialize(TargetABI().copy()))
    _check_no_kind(serialize(IRDiagnostic().copy()))
    _check_kind("MappingNote", serialize(MappingNote().copy()))
    _check_kind("ModuleImport", serialize(ModuleImport().copy()))
    _check_kind("SupportDecl", serialize(SupportDecl().copy()))
    _check_kind("ModuleDependencies", serialize(ModuleDependencies().copy()))
    _check_kind("PrimitiveDType", serialize(PrimitiveDType().copy()))
    _check_no_kind(serialize(Enumerant().copy()))
    _check_no_kind(serialize(Param().copy()))


# Round-trip: build an IntType, serialize, deserialize, and verify fields +
# that omitted default fields are filled in. This exercises the tolerant
# `deserialize_ir` shim that back-fills defaults before delegating to
# EmberJson's reflection-based `deserialize`.
def test_inttype_roundtrip_tolerant() raises:
    var src = IntType()
    src.int_kind = IntKind.UINT
    src.size_bytes = 4
    _ = serialize(src)  # exercise the serializer too

    # Drop `align_bytes` and `ext_bits` (Python's omit_if_default) and reparse.
    var sparse = '{"kind": "IntType", "int_kind": "UINT", "size_bytes": 4}'
    var got = deserialize_ir[IntType](sparse)
    assert_equal(got.int_kind, IntKind.UINT)
    assert_equal(got.size_bytes, 4)
    assert_true(got.align_bytes is None)
    assert_true(got.ext_bits is None)


# Verify .copy() produces an independent copy for an IR node.
def test_copy_is_independent() raises:
    var a = IntType()
    a.size_bytes = 4
    var b = a.copy()
    b.size_bytes = 8
    assert_equal(a.size_bytes, 4)
    assert_equal(b.size_bytes, 8)


# Verify a Pointer with nested IntType pointee round-trips through JSON, and
# that the nested Value union survives.
def test_pointer_with_nested_pointee() raises:
    var pointee = IntType()
    pointee.int_kind = IntKind.INT
    pointee.size_bytes = 4
    var ptr = Pointer()
    ptr.pointee = parse(serialize(pointee))
    ptr.size_bytes = 8
    ptr.mutability = "immut"

    var json = serialize(ptr)
    var round = deserialize_ir[Pointer](json)
    assert_equal(round.size_bytes, 8)
    assert_equal(round.mutability, "immut")
    assert_true(round.pointee is not None)
    if round.pointee:
        var p = round.pointee.value().copy()
        assert_equal(p.object()["kind"].string(), "IntType")
        assert_equal(p.object()["int_kind"].string(), "INT")
        assert_equal(p.object()["size_bytes"].int(), 4)


# Verify the Unit top-level container round-trips via to_json/from_json.
def test_unit_roundtrip() raises:
    var u = Unit()
    u.source_header = "zlib.h"
    u.library = "zlib"
    u.link_name = "z"
    u.target_abi.pointer_size_bytes = 8
    u.target_abi.pointer_align_bytes = 8
    u.target_abi.byte_order = ByteOrder.LITTLE

    var json = u.to_json[pretty=False]()
    var round = Unit.from_json(json)
    assert_equal(round.source_header, "zlib.h")
    assert_equal(round.library, "zlib")
    assert_equal(round.link_name, "z")
    assert_equal(round.target_abi.pointer_size_bytes, 8)
    assert_equal(round.target_abi.byte_order, ByteOrder.LITTLE)


def main() raises:
    test_every_node_serializes_with_kind()
    test_inttype_roundtrip_tolerant()
    test_copy_is_independent()
    test_pointer_with_nested_pointee()
    test_unit_roundtrip()
    print("OK: all ir.serde smoke tests passed")