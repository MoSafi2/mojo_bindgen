"""Tests for orphan :class:`StructRef` reachability materialization."""

from __future__ import annotations

from mojo_bindgen.analysis.reachability import (
    ReachabilityMaterializePass,
    ReachabilityOptions,
    materialize_reachable_struct_refs,
)
from mojo_bindgen.ir import (
    ByteOrder,
    Function,
    FunctionPtr,
    IntKind,
    IntType,
    Param,
    Pointer,
    Struct,
    StructRef,
    TargetABI,
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


def test_materializes_orphan_struct_ref_from_parameter() -> None:
    orphan = StructRef(
        decl_id="c:@S@external_tag",
        name="external_tag",
        c_name="external_tag",
        is_union=False,
    )
    fn = Function(
        name="use_external",
        link_name="use_external",
        ret=VoidType(),
        params=[Param(name="p", type=Pointer(pointee=orphan))],
        decl_id="c:@F@use_external",
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", target_abi=_abi(), decls=[fn])

    result = ReachabilityMaterializePass().run(unit)
    assert len(result.unit.decls) == 2
    synth = result.unit.decls[0]
    assert isinstance(synth, Struct)
    assert synth.decl_id == orphan.decl_id
    assert synth.is_complete is False
    assert synth.fields == []
    assert result.unit.decls[1] is fn
    assert result.synthesized_structs == (synth,)
    assert result.reachable_orphan_decl_ids == frozenset({orphan.decl_id})


def test_skips_when_struct_already_declared() -> None:
    orphan = StructRef(
        decl_id="c:@S@known",
        name="known",
        c_name="known",
    )
    existing = Struct(
        decl_id="c:@S@known",
        name="known",
        c_name="known",
        fields=[],
        size_bytes=0,
        align_bytes=8,
        is_complete=False,
    )
    fn = Function(
        name="f",
        link_name="f",
        ret=VoidType(),
        params=[Param(name="p", type=Pointer(pointee=orphan))],
        decl_id="c:@F@f",
    )
    unit = Unit(
        source_header="t.h",
        library="t",
        link_name="t",
        target_abi=_abi(),
        decls=[existing, fn],
    )
    result = ReachabilityMaterializePass().run(unit)
    assert result.unit.decls == unit.decls
    assert result.synthesized_structs == ()
    assert result.reachable_orphan_decl_ids == frozenset()


def test_function_ptr_traversal_finds_nested_orphan() -> None:
    inner = StructRef(
        decl_id="c:@S@cb_arg",
        name="cb_arg",
        c_name="cb_arg",
    )
    fp = FunctionPtr(
        ret=VoidType(),
        params=[Pointer(pointee=inner)],
    )
    fn = Function(
        name="register_cb",
        link_name="register_cb",
        ret=VoidType(),
        params=[Param(name="cb", type=fp)],
        decl_id="c:@F@register_cb",
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", target_abi=_abi(), decls=[fn])

    result = ReachabilityMaterializePass().run(
        unit, ReachabilityOptions(traverse_function_ptrs=True)
    )
    assert any(isinstance(d, Struct) and d.decl_id == inner.decl_id for d in result.unit.decls)
    assert inner.decl_id in result.reachable_orphan_decl_ids

    no_fp = ReachabilityMaterializePass().run(
        unit, ReachabilityOptions(traverse_function_ptrs=False)
    )
    assert no_fp.synthesized_structs == ()


def test_union_ref_skipped_by_default() -> None:
    uref = StructRef(
        decl_id="c:@U@orphan_union",
        name="orphan_union",
        c_name="orphan_union",
        is_union=True,
    )
    fn = Function(
        name="f",
        link_name="f",
        ret=VoidType(),
        params=[Param(name="p", type=Pointer(pointee=uref))],
        decl_id="c:@F@f",
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", target_abi=_abi(), decls=[fn])
    result = ReachabilityMaterializePass().run(unit)
    assert result.synthesized_structs == ()

    with_union = ReachabilityMaterializePass().run(
        unit, ReachabilityOptions(synthesize_union_refs=True)
    )
    assert len(with_union.synthesized_structs) == 1
    assert with_union.synthesized_structs[0].is_union is True


def test_materialize_reachable_struct_refs_wrapper_returns_unit_only() -> None:
    orphan = StructRef(
        decl_id="c:@S@only",
        name="only",
        c_name="only",
    )
    fn = Function(
        name="g",
        link_name="g",
        ret=VoidType(),
        params=[Param(name="x", type=Pointer(pointee=orphan))],
        decl_id="c:@F@g",
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", target_abi=_abi(), decls=[fn])
    out = materialize_reachable_struct_refs(unit)
    assert isinstance(out.decls[0], Struct)
    assert out.decls[0].decl_id == orphan.decl_id


def test_run_ir_passes_includes_reachability() -> None:
    from mojo_bindgen.analysis.orchestrator import run_ir_passes

    orphan = StructRef(
        decl_id="c:@S@pipe",
        name="pipe",
        c_name="pipe",
    )
    fn = Function(
        name="h",
        link_name="h",
        ret=_i32(),
        params=[Param(name="p", type=Pointer(pointee=orphan))],
        decl_id="c:@F@h",
    )
    unit = Unit(source_header="t.h", library="t", link_name="t", target_abi=_abi(), decls=[fn])
    out = run_ir_passes(unit)
    assert isinstance(out.decls[-1], Struct)
    assert out.decls[-1].decl_id == orphan.decl_id
