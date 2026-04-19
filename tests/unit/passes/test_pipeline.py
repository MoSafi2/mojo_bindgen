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
from mojo_bindgen.passes import AnalyzeForMojoPass, IRValidationError
from mojo_bindgen.passes.pipeline import run_ir_passes
from mojo_bindgen.passes.validate_ir import ValidateIRPass


def _i32() -> IntType:
    return IntType(int_kind=IntKind.INT, size_bytes=4, align_bytes=4)


def test_run_ir_passes_validates_already_normalized_ir() -> None:
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
