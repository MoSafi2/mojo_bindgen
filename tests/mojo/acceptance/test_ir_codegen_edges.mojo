"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_generator_emits_integer_cast_macro_as_single_scalar_call_7b2f110db7e1() raises:
    check_case("test_ir_codegen_edges/7b2f110db7e1.json.gz")


def test_incomplete_struct_emitted_as_opaque_stub_not_as_layout_struct_56a1f1112619() raises:
    check_case("test_ir_codegen_edges/56a1f1112619.json.gz")


def test_generator_emits_pure_bitfield_struct_as_storage_plus_accessors_e240ca9cdb36() raises:
    check_case("test_ir_codegen_edges/e240ca9cdb36.json.gz")


def test_generator_emits_mixed_struct_bitfields_as_storage_plus_accessors_d4d8dc9baf67() raises:
    check_case("test_ir_codegen_edges/d4d8dc9baf67.json.gz")


def test_generator_preserves_typedef_names_for_bitfield_accessors_cea1edf9efaa() raises:
    check_case("test_ir_codegen_edges/cea1edf9efaa.json.gz")


def test_generator_resets_bitfield_storage_after_zero_width_boundary_in_mixed_struct_a4acda68dadc() raises:
    check_case("test_ir_codegen_edges/a4acda68dadc.json.gz")


def test_generator_emits_zero_init_only_for_anonymous_only_pure_bitfield_struct_7582e1bd5b30() raises:
    check_case("test_ir_codegen_edges/7582e1bd5b30.json.gz")


def test_generator_omits_self_alias_typedef_for_complete_union_name_92bbd843c055() raises:
    check_case("test_ir_codegen_edges/92bbd843c055.json.gz")


def test_generator_renders_global_var_stub_and_macro_comments_b565517c82ce() raises:
    check_case("test_ir_codegen_edges/b565517c82ce.json.gz")


def test_generator_emits_macro_and_const_before_global_and_function_sections_1acf8ffa4bd8() raises:
    check_case("test_ir_codegen_edges/1acf8ffa4bd8.json.gz")


def test_generator_strips_c_float_suffix_in_macro_and_const_040a069b73c5() raises:
    check_case("test_ir_codegen_edges/040a069b73c5.json.gz")


def test_generator_imports_simd_complex_atomic_and_emits_fallback_notes_327514490783() raises:
    check_case("test_ir_codegen_edges/327514490783.json.gz")


def test_generator_imports_atomic_for_representable_atomic_types_d465d057a24d() raises:
    check_case("test_ir_codegen_edges/d465d057a24d.json.gz")


def test_generator_omits_copy_traits_and_fieldwise_init_for_atomic_struct_fields_9c0190d73a25() raises:
    check_case("test_ir_codegen_edges/9c0190d73a25.json.gz")


def test_generator_emits_global_const_wrapper_for_const_qualified_scalar_e6fab93555cf() raises:
    check_case("test_ir_codegen_edges/e6fab93555cf.json.gz")


def test_generator_preserves_typedef_names_in_fields_globals_and_aliases_5525968e9afd() raises:
    check_case("test_ir_codegen_edges/5525968e9afd.json.gz")


def test_generator_emits_function_pointer_return_wrappers_for_both_link_modes_85faea9ab837() raises:
    check_case("test_ir_codegen_edges/85faea9ab837.json.gz")


def test_generator_emits_struct_field_callback_aliases_894d79fd3ef7() raises:
    check_case("test_ir_codegen_edges/894d79fd3ef7.json.gz")


def test_generator_emits_nominal_union_alias_for_struct_arm_union_63968f1bdabc() raises:
    check_case("test_ir_codegen_edges/63968f1bdabc.json.gz")


def test_generator_emits_documented_inline_array_fallback_for_duplicated_type_union_0d8759557ca3() raises:
    check_case("test_ir_codegen_edges/0d8759557ca3.json.gz")


def test_generator_uses_callback_alias_types_in_wrapper_abi_lists_1a63371d7d6f() raises:
    check_case("test_ir_codegen_edges/1a63371d7d6f.json.gz")


def test_generator_keeps_nested_callback_typedef_in_wrapper_abi_lists_a8e54b819b45() raises:
    check_case("test_ir_codegen_edges/a8e54b819b45.json.gz")


def test_generator_emits_std_ffi_c_aliases_and_imports_by_default_43f6ee810863() raises:
    check_case("test_ir_codegen_edges/43f6ee810863.json.gz")


def test_generator_imports_std_ffi_scalars_used_only_in_callback_signatures_e44c24105582() raises:
    check_case("test_ir_codegen_edges/e44c24105582.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
