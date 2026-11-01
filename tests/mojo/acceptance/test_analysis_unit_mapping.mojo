"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_map_unit_builds_module_metadata_and_preserves_decl_order_91128f572e27() raises:
    check_case("test_analysis_unit_mapping/91128f572e27.json.gz")


def test_map_unit_uses_owned_dl_handle_module_policy_for_wrappers_06d8776fdfdb() raises:
    check_case("test_analysis_unit_mapping/06d8776fdfdb.json.gz")


def test_map_unit_maps_typedef_and_enum_surface_forms_42e2cc8c815f() raises:
    check_case("test_analysis_unit_mapping/42e2cc8c815f.json.gz")


def test_map_unit_maps_function_and_global_0667c0c37240() raises:
    check_case("test_analysis_unit_mapping/0667c0c37240.json.gz")


def test_map_unit_stubs_inline_functions_and_preserves_attrs_446d7a42d6c4() raises:
    check_case("test_analysis_unit_mapping/446d7a42d6c4.json.gz")


def test_map_unit_maps_const_and_supported_macro_to_aliases_244b32e3fbf7() raises:
    check_case("test_analysis_unit_mapping/244b32e3fbf7.json.gz")


def test_map_unit_emits_placeholder_macro_when_not_parsed_5f33bd7e5256() raises:
    check_case("test_analysis_unit_mapping/5f33bd7e5256.json.gz")


def test_map_unit_preserves_macro_with_unemitted_reference_f4a1caf46ab6() raises:
    check_case("test_analysis_unit_mapping/f4a1caf46ab6.json.gz")


def test_map_unit_preserves_macro_with_unfolded_c_logical_operator_e2223998106c() raises:
    check_case("test_analysis_unit_mapping/e2223998106c.json.gz")


def test_map_unit_maps_structs_and_unions_with_real_record_layouts_8d3e1083ade5() raises:
    check_case("test_analysis_unit_mapping/8d3e1083ade5.json.gz")


def test_map_unit_uses_unsafe_union_for_repeated_types_union_57b9c9b66c11() raises:
    check_case("test_analysis_unit_mapping/57b9c9b66c11.json.gz")


def test_map_unit_keeps_incomplete_union_as_placeholder_alias_90244efc9b5f() raises:
    check_case("test_analysis_unit_mapping/90244efc9b5f.json.gz")


def test_map_unit_maps_structs_that_store_union_members_by_named_alias_223e0ab75909() raises:
    check_case("test_analysis_unit_mapping/223e0ab75909.json.gz")


def test_map_unit_keeps_raw_callback_types_inline_7dae617268bb() raises:
    check_case("test_analysis_unit_mapping/7dae617268bb.json.gz")


def test_map_unit_synthesizes_aliases_for_external_typeref_uses_3ea606c9f8d9() raises:
    check_case("test_analysis_unit_mapping/3ea606c9f8d9.json.gz")


def test_map_unit_synthesizes_exact_width_stdint_aliases_as_fixed_width_fc279eb6c4a5() raises:
    check_case("test_analysis_unit_mapping/fc279eb6c4a5.json.gz")


def test_map_unit_maps_local_exact_width_typedef_and_chain_1485739115dd() raises:
    check_case("test_analysis_unit_mapping/1485739115dd.json.gz")


def test_map_unit_keeps_unrelated_unsigned_int_typedef_as_c_uint_b2c0637a95b0() raises:
    check_case("test_analysis_unit_mapping/b2c0637a95b0.json.gz")


def test_map_unit_keeps_ordinary_long_as_c_long_e6d599bda567() raises:
    check_case("test_analysis_unit_mapping/e6d599bda567.json.gz")


def test_map_unit_keeps_placeholder_const_when_const_expr_mapping_fails_9f1b146e84a4() raises:
    check_case("test_analysis_unit_mapping/9f1b146e84a4.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
