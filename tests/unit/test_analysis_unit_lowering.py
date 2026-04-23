"""Unit tests for the high-level CIR ``Unit`` -> MojoIR lowering entrypoint."""

from __future__ import annotations

from mojo_bindgen.analysis import lower_unit
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    Const,
    Enum,
    Enumerant,
    Field,
    Function,
    FunctionPtr,
    GlobalVar,
    IntKind,
    IntLiteral,
    IntType,
    MacroDecl,
    NullPtrLiteral,
    Pointer,
    Struct,
    StructRef,
    TargetABI,
    Typedef,
    TypeRef,
    Unit,
    VoidType,
)
from mojo_bindgen.ir import (
    Param as CIRParam,
)
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BuiltinType,
    CallbackType,
    EnumDecl,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    LinkMode,
    MojoBuiltin,
    NamedType,
    PaddingMember,
    ParametricBase,
    ParametricType,
    PointerMutability,
    PointerType,
    StoredMember,
    StructDecl,
    StructKind,
    TypeArg,
)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _abi() -> TargetABI:
    return TargetABI(pointer_size_bytes=8, pointer_align_bytes=8)


def test_lower_unit_builds_module_metadata_and_preserves_decl_order() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Typedef(
                decl_id="typedef:widget_t",
                name="widget_t",
                aliased=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                canonical=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
            ),
            Enum(
                decl_id="enum:flags",
                name="Flags",
                c_name="Flags",
                underlying=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                enumerants=[Enumerant(name="enum-value", c_name="enum-value", value=1)],
            ),
            Function(
                decl_id="fn:install",
                name="install",
                link_name="c_install",
                ret=VoidType(),
                params=[CIRParam(name="", type=Pointer(pointee=None))],
            ),
            GlobalVar(
                decl_id="global:counter",
                name="counter",
                link_name="counter",
                type=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                is_const=True,
            ),
        ],
    )

    lowered = lower_unit(unit)

    assert lowered.source_header == "demo.h"
    assert lowered.library == "demo"
    assert lowered.link_name == "demo"
    assert lowered.link_mode == LinkMode.EXTERNAL_CALL
    assert lowered.library_path_hint is None
    assert [type(decl) for decl in lowered.decls] == [AliasDecl, EnumDecl, FunctionDecl, GlobalDecl]


def test_lower_unit_uses_owned_dl_handle_module_policy_for_wrappers() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Function(
                decl_id="fn:install",
                name="install",
                link_name="c_install",
                ret=VoidType(),
                params=[CIRParam(name="", type=Pointer(pointee=None))],
            ),
        ],
    )

    lowered = lower_unit(
        unit,
        options=MojoEmitOptions(
            linking="owned_dl_handle",
            library_path_hint="/tmp/libdemo.so",
            strict_abi=True,
        ),
    )

    fn_decl = lowered.decls[0]

    assert lowered.link_mode == LinkMode.OWNED_DL_HANDLE
    assert lowered.library_path_hint == "/tmp/libdemo.so"
    assert isinstance(fn_decl, FunctionDecl)
    assert fn_decl.call_target.link_mode == LinkMode.OWNED_DL_HANDLE


def test_lower_unit_lowers_typedef_and_enum_surface_forms() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Typedef(
                decl_id="typedef:size_t",
                name="size_t",
                aliased=IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4),
                canonical=IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4),
            ),
            Enum(
                decl_id="enum:flags",
                name="Flags",
                c_name="Flags",
                underlying=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                enumerants=[Enumerant(name="needs-work", c_name="NEEDS_WORK", value=7)],
            ),
        ],
    )

    lowered = lower_unit(unit)

    typedef_decl = lowered.decls[0]
    enum_decl = lowered.decls[1]

    assert typedef_decl == AliasDecl(
        name="size_t",
        kind=AliasKind.TYPE_ALIAS,
        type_value=BuiltinType(MojoBuiltin.C_UINT),
    )
    assert isinstance(enum_decl, EnumDecl)
    assert enum_decl.name == "Flags"
    assert enum_decl.fieldwise_init is True
    assert enum_decl.enumerants[0].name == "needs_work"


def test_lower_unit_lowers_function_and_global() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Function(
                decl_id="fn:install",
                name="install",
                link_name="install",
                ret=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                params=[CIRParam(name="", type=Pointer(pointee=None))],
                is_variadic=True,
            ),
            GlobalVar(
                decl_id="global:version",
                name="version",
                link_name="version",
                type=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                is_const=True,
            ),
        ],
    )

    lowered = lower_unit(unit)

    fn_decl = lowered.decls[0]
    global_decl = lowered.decls[1]

    assert isinstance(fn_decl, FunctionDecl)
    assert fn_decl.kind == FunctionKind.VARIADIC_STUB
    assert fn_decl.params[0].name == "a0"
    assert fn_decl.call_target.symbol == "install"
    assert isinstance(global_decl, GlobalDecl)
    assert global_decl.is_const is True


def test_lower_unit_lowers_const_and_supported_macro_to_aliases() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Const(
                name="LIMIT",
                type=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
                expr=IntLiteral(42),
            ),
            MacroDecl(
                name="SHIFT",
                tokens=["42"],
                kind="object_like_supported",
                expr=IntLiteral(7),
                type=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
            ),
        ],
    )

    lowered = lower_unit(unit)

    const_decl = lowered.decls[0]
    macro_decl = lowered.decls[1]

    assert isinstance(const_decl, AliasDecl)
    assert const_decl.kind == AliasKind.CONST_VALUE
    assert const_decl.const_value is not None
    assert isinstance(macro_decl, AliasDecl)
    assert macro_decl.kind == AliasKind.MACRO_VALUE
    assert macro_decl.const_value is not None


def test_lower_unit_emits_placeholder_macro_when_not_parsed() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            MacroDecl(
                name="BROKEN",
                tokens=["foo", "(", ")"],
                kind="object_like_unsupported",
                diagnostic="unsupported macro body",
            )
        ],
    )

    lowered = lower_unit(unit)
    decl = lowered.decls[0]

    assert isinstance(decl, AliasDecl)
    assert decl.kind == AliasKind.MACRO_VALUE
    assert decl.const_value is None
    assert decl.type_value is None
    assert len(decl.diagnostics) == 2
    assert [note.category for note in decl.diagnostics] == ["macro_comment", "macro_comment"]
    assert decl.diagnostics[0].message == "macro BROKEN: unsupported macro body"
    assert decl.diagnostics[1].message == "define BROKEN foo ( )"


def test_lower_unit_lowers_structs_and_unions_with_real_record_layouts() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Struct(
                decl_id="struct:opaque",
                name="Opaque",
                c_name="Opaque",
                fields=[],
                size_bytes=0,
                align_bytes=1,
                is_complete=False,
            ),
            Struct(
                decl_id="struct:widget",
                name="Widget",
                c_name="Widget",
                fields=[],
                size_bytes=16,
                align_bytes=8,
                is_complete=True,
            ),
            Struct(
                decl_id="union:payload",
                name="Payload",
                c_name="Payload",
                fields=[
                    Field(name="a", source_name="a", type=_i32(), byte_offset=0),
                    Field(
                        name="b",
                        source_name="b",
                        type=StructRef(decl_id="struct:Widget", name="Widget", c_name="Widget"),
                        byte_offset=0,
                    ),
                ],
                size_bytes=8,
                align_bytes=8,
                is_union=True,
                is_complete=True,
            ),
        ],
    )

    lowered = lower_unit(unit)

    opaque_decl = lowered.decls[0]
    plain_decl = lowered.decls[1]
    union_decl = lowered.decls[2]

    assert isinstance(opaque_decl, StructDecl)
    assert opaque_decl.kind == StructKind.OPAQUE
    assert opaque_decl.align is None
    assert opaque_decl.align_decorator is None
    assert opaque_decl.members == []
    assert opaque_decl.diagnostics == []

    assert isinstance(plain_decl, StructDecl)
    assert plain_decl.kind == StructKind.PLAIN
    assert plain_decl.align == 8
    assert plain_decl.align_decorator == 8
    assert plain_decl.fieldwise_init is False
    assert plain_decl.members == [PaddingMember(name="__pad0", size_bytes=16, byte_offset=0)]
    assert plain_decl.diagnostics == []

    assert isinstance(union_decl, AliasDecl)
    assert union_decl.kind == AliasKind.UNION_LAYOUT
    assert union_decl.type_value == ParametricType(
        base=ParametricBase.UNSAFE_UNION,
        args=[
            TypeArg(type=BuiltinType(MojoBuiltin.C_INT)),
            TypeArg(type=NamedType("Widget")),
        ],
    )
    assert union_decl.diagnostics == []


def test_lower_unit_uses_byte_storage_fallback_for_ineligible_union() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Struct(
                decl_id="union:dup",
                name="Dup",
                c_name="Dup",
                fields=[
                    Field(name="a", source_name="a", type=_i32(), byte_offset=0),
                    Field(name="b", source_name="b", type=_i32(), byte_offset=0),
                ],
                size_bytes=4,
                align_bytes=4,
                is_union=True,
                is_complete=True,
            )
        ],
    )

    lowered = lower_unit(unit)
    union_decl = lowered.decls[0]

    assert isinstance(union_decl, AliasDecl)
    assert union_decl.kind == AliasKind.UNION_LAYOUT
    assert union_decl.type_value == ArrayType(
        element=BuiltinType(MojoBuiltin.UINT8),
        count=4,
    )
    assert union_decl.diagnostics[0].category == "union_lowering"


def test_lower_unit_keeps_incomplete_union_as_placeholder_alias() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Struct(
                decl_id="union:opaque",
                name="Opaque",
                c_name="Opaque",
                fields=[],
                size_bytes=0,
                align_bytes=1,
                is_union=True,
                is_complete=False,
            )
        ],
    )

    lowered = lower_unit(unit)
    union_decl = lowered.decls[0]

    assert isinstance(union_decl, AliasDecl)
    assert union_decl.kind == AliasKind.UNION_LAYOUT
    assert union_decl.type_value is None
    assert union_decl.diagnostics[0].category == "stub_lowering"
    assert (
        union_decl.diagnostics[0].message
        == "incomplete union placeholder emitted; layout not lowered"
    )


def test_lower_unit_lowers_structs_that_store_union_members_by_named_alias() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Struct(
                decl_id="union:payload",
                name="Payload",
                c_name="Payload",
                fields=[Field(name="value", source_name="value", type=_i32(), byte_offset=0)],
                size_bytes=8,
                align_bytes=8,
                is_union=True,
                is_complete=True,
            ),
            Struct(
                decl_id="struct:holder",
                name="Holder",
                c_name="Holder",
                fields=[
                    Field(name="tag", source_name="tag", type=_i32(), byte_offset=0),
                    Field(
                        name="payload",
                        source_name="payload",
                        type=StructRef(
                            decl_id="union:payload",
                            name="Payload",
                            c_name="Payload",
                            is_union=True,
                            size_bytes=8,
                        ),
                        byte_offset=8,
                    ),
                ],
                size_bytes=16,
                align_bytes=8,
                is_complete=True,
            ),
        ],
    )

    lowered = lower_unit(unit)
    union_decl = lowered.decls[0]
    holder_decl = lowered.decls[1]

    assert isinstance(union_decl, AliasDecl)
    assert union_decl.kind == AliasKind.UNION_LAYOUT
    assert union_decl.type_value == ParametricType(
        base=ParametricBase.UNSAFE_UNION,
        args=[TypeArg(type=BuiltinType(MojoBuiltin.C_INT))],
    )
    assert isinstance(holder_decl, StructDecl)
    assert holder_decl.kind == StructKind.PLAIN
    assert holder_decl.members == [
        StoredMember(index=0, name="tag", type=BuiltinType(MojoBuiltin.C_INT), byte_offset=0),
        StoredMember(index=1, name="payload", type=NamedType("Payload"), byte_offset=8),
    ]
    assert holder_decl.diagnostics == []


def test_lower_unit_keeps_raw_callback_types_inline() -> None:
    callback = FunctionPtr(
        ret=IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4),
        params=[Pointer(pointee=None)],
    )
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Typedef(
                decl_id="typedef:callback_t",
                name="callback_t",
                aliased=callback,
                canonical=callback,
            ),
            Function(
                decl_id="fn:install",
                name="install",
                link_name="install",
                ret=VoidType(),
                params=[CIRParam(name="cb", type=callback)],
            ),
        ],
    )

    lowered = lower_unit(unit)

    typedef_decl = lowered.decls[0]
    fn_decl = lowered.decls[1]

    assert isinstance(typedef_decl, AliasDecl)
    assert isinstance(typedef_decl.type_value, CallbackType)
    assert isinstance(fn_decl, FunctionDecl)
    assert isinstance(fn_decl.params[0].type, CallbackType)
    assert fn_decl.params[0].type.params[0].type == PointerType(
        pointee=None,
        mutability=PointerMutability.MUT,
    )


def test_lower_unit_synthesizes_aliases_for_external_typeref_uses() -> None:
    int32_ref = TypeRef(
        decl_id="typedef:int32_t",
        name="int32_t",
        canonical=_i32(),
    )
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Function(
                decl_id="fn:sf_add",
                name="sf_add",
                link_name="sf_add",
                ret=int32_ref,
                params=[
                    CIRParam(name="a", type=int32_ref),
                    CIRParam(name="b", type=int32_ref),
                ],
            ),
        ],
    )

    lowered = lower_unit(unit)
    typedef_decl = lowered.decls[0]
    fn_decl = lowered.decls[1]

    assert typedef_decl == AliasDecl(
        name="int32_t",
        kind=AliasKind.TYPE_ALIAS,
        type_value=BuiltinType(MojoBuiltin.C_INT),
    )
    assert isinstance(fn_decl, FunctionDecl)
    assert [param.type for param in fn_decl.params] == [NamedType("int32_t"), NamedType("int32_t")]
    assert fn_decl.return_type == NamedType("int32_t")


def test_lower_unit_keeps_placeholder_const_when_const_expr_lowering_fails() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Const(
                name="NULL_CB",
                type=Pointer(pointee=None),
                expr=NullPtrLiteral(),
            )
        ],
    )

    lowered = lower_unit(unit)
    decl = lowered.decls[0]

    assert isinstance(decl, AliasDecl)
    assert decl.kind == AliasKind.CONST_VALUE
    assert decl.const_value is None
    assert decl.type_value is None
    assert decl.diagnostics[0].message == (
        "constant expression could not be lowered; placeholder alias emitted"
    )
