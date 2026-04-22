"""Unit tests for CIR union -> MojoIR union layout lowering."""

from __future__ import annotations

from mojo_bindgen.ir import (
    Field,
    IntKind,
    IntType,
    Struct,
    StructRef,
    UnsupportedType,
)
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BuiltinType,
    MojoBuiltin,
    NamedType,
    ParametricBase,
    ParametricType,
    TypeArg,
)
from mojo_bindgen.new_analysis.union_lowering import lower_union


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u32() -> IntType:
    return IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)


def test_lower_union_uses_unsafe_union_for_distinct_supported_member_types() -> None:
    decl = Struct(
        decl_id="union:Payload",
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
        align_bytes=4,
        is_union=True,
        is_complete=True,
    )

    lowered = lower_union(decl)

    assert lowered == AliasDecl(
        name="Payload",
        kind=AliasKind.UNION_LAYOUT,
        type_value=ParametricType(
            base=ParametricBase.UNSAFE_UNION,
            args=[
                TypeArg(type=BuiltinType(MojoBuiltin.C_INT)),
                TypeArg(type=NamedType("Widget")),
            ],
        ),
    )


def test_lower_union_falls_back_for_duplicate_member_types() -> None:
    decl = Struct(
        decl_id="union:Dup",
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

    lowered = lower_union(decl)

    assert lowered.type_value == ArrayType(
        element=BuiltinType(MojoBuiltin.UINT8),
        count=4,
    )
    assert lowered.diagnostics[0].category == "union_lowering"
    assert "duplicates lowered type of earlier member" in lowered.diagnostics[0].message


def test_lower_union_falls_back_for_unsupported_member_type() -> None:
    decl = Struct(
        decl_id="union:Odd",
        name="Odd",
        c_name="Odd",
        fields=[
            Field(
                name="raw",
                source_name="raw",
                type=UnsupportedType(
                    category="unknown",
                    spelling="odd_t",
                    reason="not modeled",
                    size_bytes=4,
                    align_bytes=4,
                ),
                byte_offset=0,
            )
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=True,
        is_complete=True,
    )

    lowered = lower_union(decl)

    assert lowered.type_value == ArrayType(
        element=BuiltinType(MojoBuiltin.UINT8),
        count=4,
    )
    assert lowered.diagnostics[0].category == "union_lowering"
    assert "lowered to unsupported type" in lowered.diagnostics[0].message


def test_lower_union_falls_back_for_self_referential_member_type() -> None:
    decl = Struct(
        decl_id="union:Node",
        name="Node",
        c_name="Node",
        fields=[
            Field(
                name="next",
                source_name="next",
                type=StructRef(
                    decl_id="union:Node",
                    name="Node",
                    c_name="Node",
                    is_union=True,
                    size_bytes=8,
                ),
                byte_offset=0,
            )
        ],
        size_bytes=8,
        align_bytes=8,
        is_union=True,
        is_complete=True,
    )

    lowered = lower_union(decl)

    assert lowered.type_value == ArrayType(
        element=BuiltinType(MojoBuiltin.UINT8),
        count=8,
    )
    assert lowered.diagnostics[0].category == "union_lowering"
    assert "self-referential type `Node`" in lowered.diagnostics[0].message


def test_lower_union_keeps_incomplete_unions_as_placeholder_aliases() -> None:
    decl = Struct(
        decl_id="union:Opaque",
        name="Opaque",
        c_name="Opaque",
        fields=[],
        size_bytes=0,
        align_bytes=1,
        is_union=True,
        is_complete=False,
    )

    lowered = lower_union(decl)

    assert lowered.name == "Opaque"
    assert lowered.kind == AliasKind.UNION_LAYOUT
    assert lowered.type_value is None
    assert lowered.const_value is None
    assert len(lowered.diagnostics) == 1
    assert lowered.diagnostics[0].category == "stub_lowering"
    assert (
        lowered.diagnostics[0].message == "incomplete union placeholder emitted; layout not lowered"
    )
