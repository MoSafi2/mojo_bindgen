"""Round-trip tests for the standalone MojoIR schema."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="MojoIR schema is under active iteration")


def test_mojo_type_json_roundtrip() -> None:
    from mojo_bindgen.mojo_ir import (
        ArrayType,
        BuiltinType,
        FunctionType,
        MojoBuiltin,
        NamedType,
        Param,
        ParametricType,
        PointerType,
        mojo_type_from_json,
    )

    builtin = BuiltinType.from_json_dict({"kind": "BuiltinType", "name": "c_int"})
    assert isinstance(builtin, BuiltinType)
    assert builtin.name == MojoBuiltin.C_INT

    named = NamedType.from_json_dict({"kind": "NamedType", "name": "point_t"})
    assert isinstance(named, NamedType)

    ptr = PointerType.from_json_dict(
        {
            "kind": "PointerType",
            "pointee": {"kind": "BuiltinType", "name": "c_uchar"},
            "mutability": "mut",
            "origin": "external",
        }
    )
    assert isinstance(ptr, PointerType)

    array = ArrayType.from_json_dict(
        {
            "kind": "ArrayType",
            "element": {"kind": "BuiltinType", "name": "c_uchar"},
            "count": 16,
        }
    )
    assert isinstance(array, ArrayType)

    generic = ParametricType.from_json_dict(
        {
            "kind": "ParametricType",
            "base": "UnsafeUnion",
            "args": ["c_int", "point_t"],
        }
    )
    assert isinstance(generic, ParametricType)

    fn = mojo_type_from_json(
        {
            "kind": "FunctionType",
            "params": [
                {
                    "name": "lhs",
                    "type": {"kind": "BuiltinType", "name": "c_int"},
                },
                {
                    "name": "rhs",
                    "type": {"kind": "NamedType", "name": "binary_op_t"},
                },
            ],
            "ret": {"kind": "BuiltinType", "name": "c_int"},
            "abi": "C",
            "thin": True,
        }
    )
    assert isinstance(fn, FunctionType)
    assert fn.params[1] == Param(name="rhs", type=NamedType(name="binary_op_t"))
    assert fn.ret == BuiltinType(MojoBuiltin.C_INT)


def test_struct_member_json_roundtrip() -> None:
    from mojo_bindgen.mojo_ir import (
        BitfieldGroupMember,
        BuiltinType,
        MojoBuiltin,
        OpaqueStorageMember,
        PaddingMember,
        StoredMember,
        struct_member_from_json,
    )

    stored = struct_member_from_json(
        {
            "kind": "StoredMember",
            "index": 0,
            "name": "x",
            "type": {"kind": "BuiltinType", "name": "c_int"},
            "byte_offset": 0,
        }
    )
    assert isinstance(stored, StoredMember)

    padding = struct_member_from_json(
        {
            "kind": "PaddingMember",
            "name": "__pad0",
            "size_bytes": 4,
            "byte_offset": 8,
        }
    )
    assert isinstance(padding, PaddingMember)

    storage = struct_member_from_json(
        {
            "kind": "OpaqueStorageMember",
            "name": "storage",
            "size_bytes": 16,
        }
    )
    assert isinstance(storage, OpaqueStorageMember)

    bitfields = struct_member_from_json(
        {
            "kind": "BitfieldGroupMember",
            "storage_name": "__bits0",
            "storage_type": {"kind": "BuiltinType", "name": "c_uint"},
            "byte_offset": 0,
            "first_index": 0,
            "storage_width_bits": 32,
            "fields": [
                {
                    "kind": "BitfieldField",
                    "index": 0,
                    "name": "ready",
                    "logical_type": {"kind": "BuiltinType", "name": "Bool"},
                    "bit_offset": 0,
                    "bit_width": 1,
                    "signed": False,
                    "bool_semantics": True,
                },
                {
                    "kind": "BitfieldField",
                    "index": 1,
                    "name": "mode",
                    "logical_type": {"kind": "BuiltinType", "name": "c_uint"},
                    "bit_offset": 1,
                    "bit_width": 3,
                    "signed": False,
                },
            ],
        }
    )
    assert isinstance(bitfields, BitfieldGroupMember)
    assert bitfields.storage_type == BuiltinType(name=MojoBuiltin.C_UINT)
    assert bitfields.storage_width_bits == 32


def test_mojo_decl_json_roundtrip() -> None:
    from mojo_bindgen.ir import BinaryExpr, IntLiteral
    from mojo_bindgen.mojo_ir import (
        AliasDecl,
        BuiltinType,
        CallTarget,
        ComptimeMember,
        FunctionDecl,
        GlobalDecl,
        MojoBuiltin,
        MojoCallExpr,
        MojoCastExpr,
        MojoIntLiteral,
        MojoRefExpr,
        StructDecl,
        mojo_decl_from_json,
    )

    struct_decl = mojo_decl_from_json(
        {
            "kind": "StructDecl",
            "name": "point",
            "traits": ["Copyable", "Movable"],
            "align": 4,
            "fieldwise_init": True,
            "struct_kind": "plain",
            "members": [
                {
                    "kind": "StoredMember",
                    "index": 0,
                    "name": "x",
                    "type": {"kind": "BuiltinType", "name": "c_int"},
                    "byte_offset": 0,
                },
                {
                    "kind": "StoredMember",
                    "index": 1,
                    "name": "y",
                    "type": {"kind": "BuiltinType", "name": "c_int"},
                    "byte_offset": 4,
                },
            ],
            "comptime_members": [
                {
                    "kind": "ComptimeMember",
                    "name": "ORIGIN",
                    "const_value": {
                        "kind": "MojoCallExpr",
                        "callee": {"kind": "MojoRefExpr", "name": "Self"},
                        "args": [
                            {
                                "kind": "MojoCastExpr",
                                "target": {"kind": "BuiltinType", "name": "c_int"},
                                "expr": {"kind": "MojoIntLiteral", "value": 0},
                            }
                        ],
                    },
                }
            ],
            "initializers": [],
            "diagnostics": [],
        }
    )
    assert isinstance(struct_decl, StructDecl)
    assert struct_decl.comptime_members == [
        ComptimeMember(
            name="ORIGIN",
            const_value=MojoCallExpr(
                callee=MojoRefExpr("Self"),
                args=[
                    MojoCastExpr(
                        target=BuiltinType(MojoBuiltin.C_INT),
                        expr=MojoIntLiteral(0),
                    )
                ],
            ),
        )
    ]

    alias_decl = AliasDecl.from_json_dict(
        {
            "kind": "AliasDecl",
            "name": "POINT_LIMIT",
            "alias_kind": "const_value",
            "const_value": {
                "kind": "BinaryExpr",
                "op": "+",
                "lhs": {"kind": "IntLiteral", "value": 1},
                "rhs": {"kind": "IntLiteral", "value": 2},
            },
            "diagnostics": [],
        }
    )
    assert alias_decl.const_value == BinaryExpr(
        op="+",
        lhs=IntLiteral(1),
        rhs=IntLiteral(2),
    )
    assert isinstance(alias_decl, AliasDecl)

    fn_decl = mojo_decl_from_json(
        {
            "kind": "FunctionDecl",
            "name": "point_add",
            "link_name": "point_add",
            "params": [
                {
                    "kind": "Param",
                    "name": "lhs",
                    "type": {"kind": "NamedType", "name": "point"},
                },
                {
                    "kind": "Param",
                    "name": "rhs",
                    "type": {"kind": "NamedType", "name": "point"},
                },
            ],
            "return_type": {"kind": "NamedType", "name": "point"},
            "function_kind": "wrapper",
            "call_target": {
                "kind": "CallTarget",
                "link_mode": "external_call",
                "symbol": "point_add",
            },
            "diagnostics": [],
        }
    )
    assert isinstance(fn_decl, FunctionDecl)
    assert fn_decl.call_target == CallTarget(link_mode="external_call", symbol="point_add")

    global_decl = GlobalDecl.from_json_dict(
        {
            "kind": "GlobalDecl",
            "name": "global_counter",
            "link_name": "global_counter",
            "value_type": {"kind": "BuiltinType", "name": "c_int"},
            "is_const": False,
            "global_kind": "wrapper",
            "diagnostics": [],
        }
    )
    assert isinstance(global_decl, GlobalDecl)
    assert global_decl.value_type == BuiltinType(name=MojoBuiltin.C_INT)


def test_mojo_module_roundtrip() -> None:
    from mojo_bindgen.ir import BinaryExpr, IntLiteral
    from mojo_bindgen.mojo_ir import (
        AliasDecl,
        BuiltinType,
        FunctionDecl,
        FunctionType,
        GlobalDecl,
        ModuleDependencies,
        ModuleImport,
        MojoBuiltin,
        MojoModule,
        ParametricType,
        StoredMember,
        StructDecl,
        SupportDecl,
        SupportDeclKind,
    )

    module = MojoModule(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        link_mode="external_call",
        dependencies=ModuleDependencies(
            imports=[
                ModuleImport(module="std.ffi", names=["c_int"]),
                ModuleImport(module="std.builtin.simd", names=["SIMD"]),
            ],
            support_decls=[SupportDecl(SupportDeclKind.GLOBAL_SYMBOL_HELPERS)],
        ),
        decls=[
            StructDecl(
                name="demo_mode",
                kind="enum",
                members=[
                    StoredMember(
                        index=0,
                        name="value",
                        type=BuiltinType(MojoBuiltin.C_UINT),
                        byte_offset=0,
                    )
                ],
                comptime_members=[],
            ),
            AliasDecl(
                name="binary_op_t",
                kind="callback_signature",
                type_value=FunctionType(
                    params=[
                        BuiltinType(MojoBuiltin.C_INT),
                        BuiltinType(MojoBuiltin.C_INT),
                    ],
                    ret=BuiltinType(MojoBuiltin.C_INT),
                ),
            ),
            AliasDecl(
                name="DEMO_LIMIT",
                kind="const_value",
                const_value=BinaryExpr("+", IntLiteral(4), IntLiteral(5)),
            ),
            AliasDecl(
                name="demo_union",
                kind="union_layout",
                type_value=ParametricType(base="UnsafeUnion", args=["c_int", "point"]),
            ),
            FunctionDecl(
                name="demo_add",
                link_name="demo_add",
                return_type=BuiltinType(MojoBuiltin.C_INT),
            ),
            GlobalDecl(
                name="demo_counter",
                link_name="demo_counter",
                value_type=BuiltinType(MojoBuiltin.C_INT),
            ),
        ],
    )

    raw = module.to_json_dict()
    restored = MojoModule.from_json_dict(raw)
    assert restored.to_json_dict() == raw


def test_unknown_mojo_type_kind_raises() -> None:
    from mojo_bindgen.mojo_ir import mojo_type_from_json

    with pytest.raises(ValueError) as exc_info:
        mojo_type_from_json({"kind": "NoSuchMojoType"})
    assert "NoSuchMojoType" in str(exc_info.value)


def test_builtin_lookup_tables_cover_expected_scalars() -> None:
    from mojo_bindgen.ir import FloatKind, IntKind
    from mojo_bindgen.mojo_ir import PRIMITIVE_BUILTINS, MojoBuiltin

    assert PRIMITIVE_BUILTINS["void"] == MojoBuiltin.NONE
    assert PRIMITIVE_BUILTINS[IntKind.BOOL] == MojoBuiltin.BOOL
    assert PRIMITIVE_BUILTINS[IntKind.INT] == MojoBuiltin.C_INT
    assert PRIMITIVE_BUILTINS[IntKind.ULONG] == MojoBuiltin.C_ULONG
    assert PRIMITIVE_BUILTINS[FloatKind.FLOAT] == MojoBuiltin.C_FLOAT
    assert PRIMITIVE_BUILTINS[FloatKind.DOUBLE] == MojoBuiltin.C_DOUBLE


def test_unknown_struct_member_kind_raises() -> None:
    from mojo_bindgen.mojo_ir import struct_member_from_json

    with pytest.raises(ValueError) as exc_info:
        struct_member_from_json({"kind": "NoSuchStructMember"})
    assert "NoSuchStructMember" in str(exc_info.value)


def test_unknown_mojo_decl_kind_raises() -> None:
    from mojo_bindgen.mojo_ir import mojo_decl_from_json

    with pytest.raises(ValueError) as exc_info:
        mojo_decl_from_json({"kind": "NoSuchMojoDecl"})
    assert "NoSuchMojoDecl" in str(exc_info.value)
