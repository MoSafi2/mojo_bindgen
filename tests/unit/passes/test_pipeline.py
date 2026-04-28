from __future__ import annotations

import pytest

from mojo_bindgen.analysis import lower_unit, run_ir_passes
from mojo_bindgen.analysis.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.analysis.validate_ir import IRValidationError, ValidateIRPass
from mojo_bindgen.ir import (
    ByteOrder,
    Field,
    Function,
    IntKind,
    IntType,
    Param,
    Struct,
    TargetABI,
    Typedef,
    TypeRef,
    Unit,
    VoidType,
)
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    BuiltinType,
    FunctionDecl,
    MojoBuiltin,
    NamedType,
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
