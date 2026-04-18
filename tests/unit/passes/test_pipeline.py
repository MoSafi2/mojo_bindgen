from __future__ import annotations

import pytest

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.ir import (
    Field,
    Function,
    IntKind,
    IntType,
    Param,
    Pointer,
    Struct,
    StructRef,
    TypeRef,
    Typedef,
    Unit,
    VoidType,
)
from mojo_bindgen.passes import AnalyzeForMojoPass, IRValidationError, NormalizeTypeRefsPass
from mojo_bindgen.passes.pipeline import run_ir_passes
from mojo_bindgen.passes.resolve_decl_refs import ResolveDeclRefsPass
from mojo_bindgen.passes.validate_ir import ValidateIRPass


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def test_normalize_type_refs_pass_returns_rebuilt_unit() -> None:
    i32 = _i32()
    td = Typedef(decl_id="typedef:my_int", name="my_int", aliased=i32, canonical=i32)
    tr = TypeRef(decl_id=td.decl_id, name=td.name, canonical=i32)
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
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

    normalized = NormalizeTypeRefsPass().run(unit)
    assert normalized is not unit
    assert normalized.decls[1] is not unit.decls[1]
    field_type = normalized.decls[1].fields[0].type
    assert isinstance(field_type, TypeRef)
    assert field_type.name == "my_int"
    assert isinstance(field_type.canonical, IntType)


def test_normalize_type_refs_pass_unrolls_nested_typedef_canonical_chain() -> None:
    i32 = _i32()
    inner = Typedef(decl_id="typedef:inner", name="inner", aliased=i32, canonical=i32)
    inner_ref = TypeRef(decl_id=inner.decl_id, name=inner.name, canonical=i32)
    outer = Typedef(
        decl_id="typedef:outer",
        name="outer",
        aliased=inner_ref,
        canonical=inner_ref,
    )
    outer_ref = TypeRef(decl_id=outer.decl_id, name=outer.name, canonical=inner_ref)
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            inner,
            outer,
            Struct(
                decl_id="struct:holder",
                name="holder",
                c_name="holder",
                fields=[Field(name="x", source_name="x", type=outer_ref, byte_offset=0)],
                size_bytes=4,
                align_bytes=4,
            ),
        ],
    )

    normalized = NormalizeTypeRefsPass().run(unit)
    outer_td = normalized.decls[1]
    field_type = normalized.decls[2].fields[0].type
    assert isinstance(outer_td, Typedef)
    assert isinstance(outer_td.canonical, IntType)
    assert isinstance(field_type, TypeRef)
    assert isinstance(field_type.canonical, IntType)


def test_resolve_decl_refs_pass_fills_blank_function_decl_id() -> None:
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            Function(
                name="work",
                link_name="work",
                ret=VoidType(),
                params=[],
                decl_id="",
            )
        ],
    )

    resolved = ResolveDeclRefsPass().run(unit)
    fn = resolved.decls[0]
    assert isinstance(fn, Function)
    assert fn.decl_id == "work"


def test_resolve_decl_refs_pass_repairs_struct_ref_by_name() -> None:
    node = Struct(
        decl_id="struct:node",
        name="node",
        c_name="node",
        fields=[],
        size_bytes=0,
        align_bytes=8,
        is_complete=False,
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            node,
            Function(
                decl_id="fn:take",
                name="take",
                link_name="take",
                ret=VoidType(),
                params=[
                    Param(
                        name="n",
                        type=Pointer(
                            pointee=StructRef(
                                decl_id="",
                                name="node",
                                c_name="",
                                size_bytes=0,
                            )
                        ),
                    )
                ],
            ),
        ],
    )

    resolved = ResolveDeclRefsPass().run(unit)
    fn = resolved.decls[1]
    pointee = fn.params[0].type.pointee
    assert isinstance(pointee, StructRef)
    assert pointee.decl_id == node.decl_id
    assert pointee.c_name == node.c_name


def test_validate_ir_pass_rejects_duplicate_decl_ids() -> None:
    i32 = _i32()
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        decls=[
            Typedef(decl_id="typedef:dup", name="a", aliased=i32, canonical=i32),
            Typedef(decl_id="typedef:dup", name="b", aliased=i32, canonical=i32),
        ],
    )

    with pytest.raises(IRValidationError) as exc_info:
        ValidateIRPass().run(unit)
    assert "duplicate decl_id" in str(exc_info.value)


def test_run_ir_passes_and_analyze_for_mojo_produce_analyzed_unit() -> None:
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
    unit = Unit(source_header="t.h", library="t", link_name="t", decls=[td, fn])

    normalized = run_ir_passes(unit)
    analyzed = AnalyzeForMojoPass(MojoEmitOptions()).run(normalized)
    assert analyzed.unit is normalized
    assert "my_int" in analyzed.emitted_typedef_mojo_names
