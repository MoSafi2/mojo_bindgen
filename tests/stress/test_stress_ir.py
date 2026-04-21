"""IR-focused checks for pathological stress fixtures."""

from __future__ import annotations

import json

import pytest

from mojo_bindgen.ir import (
    Array,
    Function,
    GlobalVar,
    MacroDecl,
    Pointer,
    Struct,
    StructRef,
    Typedef,
    Unit,
)

from tests.stress._helpers import case_dirs, has_libclang, parse_case

pytestmark = pytest.mark.skipif(
    not has_libclang(),
    reason="libclang not available (use pixi run)",
)


@pytest.mark.parametrize("case_dir", case_dirs(), ids=lambda path: path.name)
def test_stress_fixture_json_round_trip(case_dir) -> None:
    unit = parse_case(case_dir)
    d0 = unit.to_json_dict()
    d1 = json.loads(json.dumps(d0))
    d2 = Unit.from_json_dict(d1).to_json_dict()
    assert d0 == d2


def test_pathological_core_preserves_selected_hard_declarations() -> None:
    unit = parse_case(next(path for path in case_dirs() if path.name == "pathological_core"))

    typedefs = {decl.name: decl for decl in unit.decls if isinstance(decl, Typedef)}
    globals_by_name = {decl.name: decl for decl in unit.decls if isinstance(decl, GlobalVar)}
    functions = {decl.name: decl for decl in unit.decls if isinstance(decl, Function)}
    structs_by_id = {decl.decl_id: decl for decl in unit.decls if isinstance(decl, Struct)}

    assert {"pc_callback_t", "pc_callback_alias_t", "pc_callback_chain_t"} <= typedefs.keys()
    assert {"pc_choose_callback", "pc_pick_transform", "pc_complex_mul"} <= functions.keys()
    assert {
        "pc_global_incomplete",
        "pc_global_union",
        "pc_global_payload",
        "pc_ptr_to_array",
    } <= globals_by_name.keys()

    incomplete = globals_by_name["pc_global_incomplete"]
    assert isinstance(incomplete.type, Pointer)
    assert isinstance(incomplete.type.pointee, StructRef)
    assert incomplete.type.pointee.size_bytes == 0

    payload = globals_by_name["pc_global_payload"]
    assert isinstance(payload.type, StructRef)
    assert payload.type.is_union is True
    assert payload.type.size_bytes == 16

    outer = next(
        decl for decl in unit.decls if isinstance(decl, Struct) and decl.name == "pc_nested_anon"
    )
    anon_union_ref = next(
        field.type
        for field in outer.fields
        if field.is_anonymous and isinstance(field.type, StructRef) and field.type.is_union
    )
    anon_union = structs_by_id[anon_union_ref.decl_id]
    assert anon_union.is_union is True
    assert len(anon_union.fields) == 2
    assert all(field.is_anonymous for field in anon_union.fields)


def test_pathological_macros_preserves_supported_and_unsupported_forms() -> None:
    unit = parse_case(next(path for path in case_dirs() if path.name == "pathological_macros"))
    macros = {decl.name: decl for decl in unit.decls if isinstance(decl, MacroDecl)}

    assert {"PM_INT", "PM_FILE", "PM_EMPTY", "PM_FUNC", "PM_GENERIC"} <= macros.keys()

    assert macros["PM_INT"].kind == "object_like_supported"
    assert macros["PM_INT"].expr is not None
    assert macros["PM_FILE"].kind == "predefined"
    assert macros["PM_FILE"].tokens == ["__FILE__"]
    assert macros["PM_EMPTY"].kind == "empty"
    assert macros["PM_EMPTY"].tokens == []
    assert macros["PM_FUNC"].kind == "function_like_unsupported"
    assert macros["PM_FUNC"].diagnostic is not None
    assert macros["PM_GENERIC"].kind == "object_like_unsupported"
    assert macros["PM_GENERIC"].diagnostic is not None


def test_pathological_layout_preserves_selected_layout_edges() -> None:
    unit = parse_case(next(path for path in case_dirs() if path.name == "pathological_layout"))
    structs = {decl.name: decl for decl in unit.decls if isinstance(decl, Struct)}

    dense = structs["pl_dense_bits"]
    assert any(field.is_bitfield and field.bit_width == 0 for field in dense.fields)

    pure = structs["pl_pure_bits"]
    assert pure.fields
    assert all(field.is_bitfield for field in pure.fields)

    packed = structs["pl_packed_header"]
    assert packed.is_packed is True

    explicit = structs["pl_explicit_align"]
    assert explicit.requested_align_bytes == 16

    field_align = structs["pl_field_align"]
    assert field_align.align_bytes == 16
    assert field_align.requested_align_bytes is None

    flex = structs["pl_flex"].fields[-1].type
    assert isinstance(flex, Array)
    assert flex.array_kind == "flexible"

    incomplete = structs["pl_incomplete_array"].fields[-1].type
    assert isinstance(incomplete, Array)
    assert incomplete.size == 0
