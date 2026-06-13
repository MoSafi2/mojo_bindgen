"""Unit tests for CIR union -> MojoIR union layout mapping."""

from __future__ import annotations

from mojo_bindgen.analysis.mojo.union_mapping import map_union
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    Array,
    BuiltinType,
    Field,
    IntKind,
    IntType,
    MojoBuiltin,
    NamedType,
    ParametricBase,
    ParametricType,
    Struct,
    StructRef,
    TypeArg,
    UnsupportedType,
)


def _i16() -> IntType:
    return IntType(int_kind=IntKind.SHORT, size_bytes=2, align_bytes=4)


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def _u32() -> IntType:
    return IntType(int_kind=IntKind.UINT, size_bytes=4, align_bytes=4)


def test_map_union_uses_unsafe_union_for_distinct_supported_member_types() -> None:
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

    mapped = map_union(decl)

    assert mapped == AliasDecl(
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


def test_map_union_falls_back_for_duplicate_member_types() -> None:
    decl = Struct(
        decl_id="union:Dup",
        name="Dup",
        c_name="Dup",
        fields=[
            Field(name="a", source_name="a", type=_i32(), byte_offset=0),
            Field(name="b", source_name="b", type=_i32(), byte_offset=0),
            Field(name="c", source_name="c", type=_i16(), byte_offset=0),
        ],
        size_bytes=4,
        align_bytes=4,
        is_union=True,
        is_complete=True,
    )

    mapped = map_union(decl)

    assert mapped.type_value == ParametricType(
        base=ParametricBase.UNSAFE_UNION,
        args=[
            TypeArg(type=BuiltinType(MojoBuiltin.C_INT)),
            TypeArg(type=BuiltinType(MojoBuiltin.C_SHORT)),
        ],
    )
    assert mapped.diagnostics[0].category == "union_mapping"
    assert "duplicates mapped type of earlier member" in mapped.diagnostics[0].message


def test_map_union_falls_back_for_unsupported_member_type() -> None:
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

    mapped = map_union(decl)

    assert mapped.type_value == ParametricType(
        base=ParametricBase.UNSAFE_UNION,
        args=[
            TypeArg(
                type=Array(
                    element=BuiltinType(MojoBuiltin.UINT8),
                    size=4,
                )
            )
        ],
    )
    assert mapped.diagnostics == []


def test_map_union_falls_back_for_self_referential_member_type() -> None:
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

    mapped = map_union(decl)

    assert mapped.type_value == Array(
        element=BuiltinType(MojoBuiltin.UINT8),
        size=8,
    )
    assert mapped.diagnostics[0].category == "union_mapping"
    assert "self-referential type `Node`" in mapped.diagnostics[0].message


def test_map_union_keeps_incomplete_unions_as_placeholder_aliases() -> None:
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

    mapped = map_union(decl)

    assert mapped.name == "Opaque"
    assert mapped.kind == AliasKind.UNION_LAYOUT
    assert mapped.type_value is None
    assert mapped.const_value is None
    assert len(mapped.diagnostics) == 1
    assert mapped.diagnostics[0].category == "stub_mapping"
    assert (
        mapped.diagnostics[0].message == "incomplete union placeholder emitted; layout not mapped"
    )
