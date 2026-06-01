from __future__ import annotations

import pytest

from mojo_bindgen.analysis import lower_unit, run_ir_passes
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.validate_ir import IRValidationError, ValidateIRPass
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    BuiltinType,
    ByteOrder,
    CallExpr,
    CastExpr,
    Enum,
    Enumerant,
    EnumRef,
    Field,
    Function,
    FunctionDecl,
    IntKind,
    IntLiteral,
    IntType,
    MojoBuiltin,
    NamedType,
    Param,
    RefExpr,
    Struct,
    TargetABI,
    Typedef,
    TypeRef,
    Unit,
    VoidType,
)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _abi() -> TargetABI:
    return TargetABI(
        pointer_size_bytes=8,
        pointer_align_bytes=8,
        byte_order=ByteOrder.LITTLE,
    )


def test_run_ir_passes_validates_already_normalized_ir() -> None:
    i32 = _i32()
    td = Typedef(decl_id="typedef:my_int", name="my_int", aliased=i32, canonical=i32)
    tr = TypeRef(decl_id=td.decl_id, name=td.name, canonical=i32)
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        target_abi=_abi(),
        decls=[
            td,
            Struct(
                decl_id="struct:holder",
                name="holder",
                c_name="holder",
                fields=[Field(name="x", source_name="x", type=tr, byte_offset=0)],
                size_bytes=4,
                align_bytes=4,
            ),
        ],
    )

    normalized = run_ir_passes(unit)
    assert normalized is unit
    field_type = normalized.decls[1].fields[0].type
    assert isinstance(field_type, TypeRef)
    assert field_type.name == "my_int"
    assert isinstance(field_type.canonical, IntType)


def test_validate_ir_pass_rejects_duplicate_decl_ids() -> None:
    i32 = _i32()
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        target_abi=_abi(),
        decls=[
            Typedef(decl_id="typedef:dup", name="a", aliased=i32, canonical=i32),
            Typedef(decl_id="typedef:dup", name="b", aliased=i32, canonical=i32),
        ],
    )

    with pytest.raises(IRValidationError) as exc_info:
        ValidateIRPass().run(unit)
    assert "duplicate decl_id" in str(exc_info.value)


def test_run_ir_passes_and_lower_unit_preserve_typedef_surface_name() -> None:
    i32 = _i32()
    td = Typedef(decl_id="typedef:my_int", name="my_int", aliased=i32, canonical=i32)
    tr = TypeRef(decl_id=td.decl_id, name=td.name, canonical=i32)
    fn = Function(
        decl_id="fn:take",
        name="take",
        link_name="take",
        ret=VoidType(),
        params=[Param(name="x", type=tr)],
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", target_abi=_abi(), decls=[td, fn])

    normalized = run_ir_passes(unit)
    lowered = lower_unit(normalized, options=MojoEmitOptions())
    typedef_decl = lowered.decls[0]
    fn_decl = lowered.decls[1]

    assert typedef_decl == AliasDecl(
        name="my_int",
        kind=AliasKind.TYPE_ALIAS,
        type_value=BuiltinType(MojoBuiltin.C_INT),
    )
    assert isinstance(fn_decl, FunctionDecl)
    assert [param.type for param in fn_decl.params] == [NamedType("my_int")]
    assert fn_decl.return_type == BuiltinType(MojoBuiltin.NONE)


def test_run_ir_passes_prefers_typedef_name_for_named_enum_and_emits_tag_alias() -> None:
    enum_int = IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)
    enum_ref = EnumRef(
        decl_id="enum:tag_name",
        name="tag_name",
        c_name="tag_name",
        underlying=enum_int,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        target_abi=_abi(),
        decls=[
            Enum(
                decl_id="enum:tag_name",
                name="tag_name",
                c_name="tag_name",
                underlying=enum_int,
                enumerants=[Enumerant(name="TAG_A", c_name="TAG_A", value=3)],
            ),
            Typedef(
                decl_id="typedef:typedef_name",
                name="typedef_name",
                aliased=enum_ref,
                canonical=enum_ref,
            ),
            Function(
                decl_id="fn:take",
                name="take",
                link_name="take",
                ret=VoidType(),
                params=[
                    Param(
                        name="mode",
                        type=TypeRef(
                            decl_id="typedef:typedef_name",
                            name="typedef_name",
                            canonical=enum_ref,
                        ),
                    )
                ],
            ),
        ],
    )

    normalized = run_ir_passes(unit)
    enum_decl = normalized.decls[0]
    assert isinstance(enum_decl, Enum)
    assert enum_decl.name == "typedef_name"
    assert enum_decl.alias_names == ["tag_name"]

    lowered = lower_unit(normalized, options=MojoEmitOptions())
    assert lowered.decls[0] == AliasDecl(
        name="typedef_name",
        kind=AliasKind.TYPE_ALIAS,
        type_value=BuiltinType(MojoBuiltin.C_UINT),
    )
    assert lowered.decls[1] == AliasDecl(
        name="tag_name",
        kind=AliasKind.TYPE_ALIAS,
        type_value=NamedType("typedef_name"),
    )
    assert lowered.decls[2] == AliasDecl(
        name="TAG_A",
        kind=AliasKind.CONST_VALUE,
        const_type=NamedType("typedef_name"),
        const_value=CallExpr(
            callee=RefExpr("typedef_name"),
            args=[
                CastExpr(
                    target=BuiltinType(MojoBuiltin.C_UINT),
                    expr=IntLiteral(3),
                )
            ],
        ),
    )
    assert isinstance(lowered.decls[3], FunctionDecl)
    assert lowered.decls[3].params[0].type == NamedType("typedef_name")


def test_run_ir_passes_uses_tag_name_for_tag_only_enum() -> None:
    enum_int = IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)
    enum_ref = EnumRef(
        decl_id="enum:mode_tag",
        name="mode_tag",
        c_name="mode_tag",
        underlying=enum_int,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        target_abi=_abi(),
        decls=[
            Enum(
                decl_id="enum:mode_tag",
                name="mode_tag",
                c_name="mode_tag",
                underlying=enum_int,
                enumerants=[Enumerant(name="MODE_A", c_name="MODE_A", value=1)],
            ),
            Function(
                decl_id="fn:get_mode",
                name="get_mode",
                link_name="get_mode",
                ret=enum_ref,
                params=[],
            ),
        ],
    )

    normalized = run_ir_passes(unit)
    enum_decl = normalized.decls[0]
    assert isinstance(enum_decl, Enum)
    assert enum_decl.name == "mode_tag"
    assert enum_decl.alias_names == []

    lowered = lower_unit(normalized, options=MojoEmitOptions())
    assert lowered.decls[0] == AliasDecl(
        name="mode_tag",
        kind=AliasKind.TYPE_ALIAS,
        type_value=BuiltinType(MojoBuiltin.C_UINT),
    )
    assert lowered.decls[1] == AliasDecl(
        name="MODE_A",
        kind=AliasKind.CONST_VALUE,
        const_type=NamedType("mode_tag"),
        const_value=CallExpr(
            callee=RefExpr("mode_tag"),
            args=[
                CastExpr(
                    target=BuiltinType(MojoBuiltin.C_UINT),
                    expr=IntLiteral(1),
                )
            ],
        ),
    )
    assert isinstance(lowered.decls[2], FunctionDecl)
    assert lowered.decls[2].return_type == NamedType("mode_tag")


def test_run_ir_passes_drops_colliding_tag_alias_for_typedef_enum() -> None:
    enum_int = IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)
    enum_ref = EnumRef(
        decl_id="enum:mode_t",
        name="mode_t",
        c_name="mode_t",
        underlying=enum_int,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        target_abi=_abi(),
        decls=[
            Enum(
                decl_id="enum:mode_t",
                name="mode_t",
                c_name="mode_t",
                underlying=enum_int,
                enumerants=[Enumerant(name="MODE_A", c_name="MODE_A", value=1)],
            ),
            Typedef(
                decl_id="typedef:mode_t",
                name="mode_t",
                aliased=enum_ref,
                canonical=enum_ref,
            ),
        ],
    )

    normalized = run_ir_passes(unit)
    enum_decl = normalized.decls[0]
    assert isinstance(enum_decl, Enum)
    assert enum_decl.name == "mode_t"
    assert enum_decl.alias_names == []

    lowered = lower_unit(normalized, options=MojoEmitOptions())
    assert lowered.decls == [
        AliasDecl(
            name="mode_t",
            kind=AliasKind.TYPE_ALIAS,
            type_value=BuiltinType(MojoBuiltin.C_UINT),
        ),
        AliasDecl(
            name="MODE_A",
            kind=AliasKind.CONST_VALUE,
            const_type=NamedType("mode_t"),
            const_value=CallExpr(
                callee=RefExpr("mode_t"),
                args=[
                    CastExpr(
                        target=BuiltinType(MojoBuiltin.C_UINT),
                        expr=IntLiteral(1),
                    )
                ],
            ),
        ),
    ]
