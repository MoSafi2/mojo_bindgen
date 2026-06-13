from __future__ import annotations

import pytest

from mojo_bindgen.analysis import (
    AliasClass,
    ReferenceValidationError,
    ValidateReferencesPass,
    build_analysis_context,
)
from mojo_bindgen.ir import (
    ByteOrder,
    EnumRef,
    Field,
    Function,
    FunctionPtr,
    IntKind,
    IntType,
    MacroDecl,
    Param,
    RefExpr,
    Struct,
    StructRef,
    TargetABI,
    Typedef,
    TypeRef,
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


def test_analysis_context_classifies_aliases_and_builds_dependency_graph() -> None:
    i32 = _i32()
    callback = Typedef(
        decl_id="typedef:callback_t",
        name="callback_t",
        aliased=FunctionPtr(ret=VoidType(), params=[Param(name="value", type=i32)]),
        canonical=FunctionPtr(ret=VoidType(), params=[Param(name="value", type=i32)]),
    )
    payload = Struct(
        decl_id="struct:Payload",
        name="Payload",
        c_name="Payload",
        fields=[Field(name="value", source_name="value", type=i32, byte_offset=0, size_bytes=4)],
        size_bytes=4,
        align_bytes=4,
        is_complete=True,
    )
    external_ref = TypeRef(
        decl_id="typedef:external_size",
        name="external_size",
        canonical=i32,
    )
    function = Function(
        decl_id="fn:take",
        name="take",
        link_name="take",
        ret=VoidType(),
        params=[
            Param(
                name="payload",
                type=StructRef(
                    decl_id=payload.decl_id,
                    name=payload.name,
                    c_name=payload.c_name,
                    size_bytes=payload.size_bytes,
                    align_bytes=payload.align_bytes,
                ),
            ),
            Param(name="size", type=external_ref),
        ],
    )
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[callback, payload, function],
    )

    context = build_analysis_context(unit)

    assert context.alias_classification.aliases_by_decl_id[callback.decl_id].alias_class == (
        AliasClass.CALLBACK
    )
    assert (
        context.alias_classification.external_aliases_by_decl_id[external_ref.decl_id].alias_class
        == AliasClass.EXTERNAL_TYPEDEF
    )
    assert context.dependency_graph.edges_by_decl_id[function.decl_id] == frozenset(
        {payload.decl_id, external_ref.decl_id}
    )
    assert context.record_storage[payload.decl_id].uses_typed_storage is True


def test_validate_references_rejects_missing_enum_refs() -> None:
    missing_enum = EnumRef(
        decl_id="enum:Missing",
        name="Missing",
        c_name="Missing",
        underlying=_i32(),
    )
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Function(
                decl_id="fn:get",
                name="get",
                link_name="get",
                ret=missing_enum,
                params=[],
            )
        ],
    )

    with pytest.raises(ReferenceValidationError, match="EnumRef"):
        ValidateReferencesPass().run(unit)


def test_dependency_graph_tracks_const_symbol_edges() -> None:
    unit = Unit(
        source_header="demo.h",
        library="demo",
        link_name="demo",
        target_abi=_abi(),
        decls=[
            Typedef(
                decl_id="typedef:my_int",
                name="my_int",
                aliased=_i32(),
                canonical=_i32(),
            ),
            Function(
                decl_id="fn:f",
                name="f",
                link_name="f",
                ret=VoidType(),
                params=[Param(name="x", type=_i32())],
            ),
        ],
    )
    unit.decls.append(
        MacroDecl(
            name="ALIAS",
            tokens=["OTHER"],
            kind="object_like_supported",
            expr=RefExpr("OTHER"),
            type=_i32(),
        )
    )

    context = build_analysis_context(unit)

    assert context.dependency_graph.symbol_edges_by_decl_id["ALIAS"] == frozenset({"OTHER"})
