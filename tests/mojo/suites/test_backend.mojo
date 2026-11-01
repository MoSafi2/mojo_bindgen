"""Fixed subsystem suite; individual files remain independently runnable."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case


from acceptance.test_analysis_const_mapping import (
    test_map_const_expr_maps_binary_ref_cast_and_sizeof_nodes_83464734ef41,
)
from acceptance.test_analysis_const_mapping import (
    test_map_const_expr_parses_decimal_and_hex_float_literals_b18580b08584,
)
from acceptance.test_analysis_const_mapping import test_map_float_numeric_edges_9989d78b8e69
from acceptance.test_analysis_const_mapping import test_map_float_numeric_edges_fce5e0c6f07c
from acceptance.test_analysis_const_mapping import test_map_float_numeric_edges_485e1e9c90f6
from acceptance.test_analysis_const_mapping import test_map_float_numeric_edges_54dcb952e2c1
from acceptance.test_analysis_const_mapping import test_map_float_numeric_edges_f02c5a7947bb
from acceptance.test_analysis_const_mapping import test_map_float_numeric_edges_3bd46e2f9065
from acceptance.test_analysis_const_mapping import (
    test_expression_mapping_recovers_after_rejected_nullptr_41cee805a0b8,
)
from acceptance.test_analysis_const_mapping import (
    test_recursive_expression_mapping_preserves_shared_inputs_bc3bc879a0db,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_builds_module_metadata_and_preserves_decl_order_91128f572e27,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_uses_owned_dl_handle_module_policy_for_wrappers_06d8776fdfdb,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_maps_typedef_and_enum_surface_forms_42e2cc8c815f,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_maps_function_and_global_0667c0c37240,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_stubs_inline_functions_and_preserves_attrs_446d7a42d6c4,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_maps_const_and_supported_macro_to_aliases_244b32e3fbf7,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_emits_placeholder_macro_when_not_parsed_5f33bd7e5256,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_preserves_macro_with_unemitted_reference_f4a1caf46ab6,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_preserves_macro_with_unfolded_c_logical_operator_e2223998106c,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_maps_structs_and_unions_with_real_record_layouts_8d3e1083ade5,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_uses_unsafe_union_for_repeated_types_union_57b9c9b66c11,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_keeps_incomplete_union_as_placeholder_alias_90244efc9b5f,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_maps_structs_that_store_union_members_by_named_alias_223e0ab75909,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_keeps_raw_callback_types_inline_7dae617268bb,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_synthesizes_aliases_for_external_typeref_uses_3ea606c9f8d9,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_synthesizes_exact_width_stdint_aliases_as_fixed_width_fc279eb6c4a5,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_maps_local_exact_width_typedef_and_chain_1485739115dd,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_keeps_unrelated_unsigned_int_typedef_as_c_uint_b2c0637a95b0,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_keeps_ordinary_long_as_c_long_e6d599bda567,
)
from acceptance.test_analysis_unit_mapping import (
    test_map_unit_keeps_placeholder_const_when_const_expr_mapping_fails_9f1b146e84a4,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_integer_cast_macro_as_single_scalar_call_7b2f110db7e1,
)
from acceptance.test_ir_codegen_edges import (
    test_incomplete_struct_emitted_as_opaque_stub_not_as_layout_struct_56a1f1112619,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_pure_bitfield_struct_as_storage_plus_accessors_e240ca9cdb36,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_mixed_struct_bitfields_as_storage_plus_accessors_d4d8dc9baf67,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_preserves_typedef_names_for_bitfield_accessors_cea1edf9efaa,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_resets_bitfield_storage_after_zero_width_boundary_in_mixed_struct_a4acda68dadc,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_zero_init_only_for_anonymous_only_pure_bitfield_struct_7582e1bd5b30,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_omits_self_alias_typedef_for_complete_union_name_92bbd843c055,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_renders_global_var_stub_and_macro_comments_b565517c82ce,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_macro_and_const_before_global_and_function_sections_1acf8ffa4bd8,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_strips_c_float_suffix_in_macro_and_const_040a069b73c5,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_imports_simd_complex_atomic_and_emits_fallback_notes_327514490783,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_imports_atomic_for_representable_atomic_types_d465d057a24d,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_omits_copy_traits_and_fieldwise_init_for_atomic_struct_fields_9c0190d73a25,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_global_const_wrapper_for_const_qualified_scalar_e6fab93555cf,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_preserves_typedef_names_in_fields_globals_and_aliases_5525968e9afd,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_function_pointer_return_wrappers_for_both_link_modes_85faea9ab837,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_struct_field_callback_aliases_894d79fd3ef7,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_nominal_union_alias_for_struct_arm_union_63968f1bdabc,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_documented_inline_array_fallback_for_duplicated_type_union_0d8759557ca3,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_uses_callback_alias_types_in_wrapper_abi_lists_1a63371d7d6f,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_keeps_nested_callback_typedef_in_wrapper_abi_lists_a8e54b819b45,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_emits_std_ffi_c_aliases_and_imports_by_default_43f6ee810863,
)
from acceptance.test_ir_codegen_edges import (
    test_generator_imports_std_ffi_scalars_used_only_in_callback_signatures_e44c24105582,
)
from acceptance.test_layout_tests import (
    test_collect_layout_record_checks_for_plain_struct_with_padding_95eab877197d,
)
from acceptance.test_layout_tests import (
    test_collect_layout_record_checks_uses_emitted_indices_after_bitfield_padding_ab3247cc497b,
)
from acceptance.test_layout_tests import (
    test_collect_layout_record_checks_for_opaque_storage_skips_field_offsets_ac6b7d212475,
)
from acceptance.test_layout_tests import (
    test_collect_layout_record_checks_for_bitfield_storage_group_offset_6fc2f0faadc4,
)
from acceptance.test_layout_tests import (
    test_collect_layout_record_checks_uses_emitted_indices_for_bitfield_groups_647bb25621a0,
)
from acceptance.test_layout_tests import (
    test_collect_layout_record_checks_skips_incomplete_union_and_missing_record_decl_159553085b0c,
)
from acceptance.test_layout_tests import (
    test_render_layout_test_module_imports_records_and_calls_tests_8f223049082c,
)
from acceptance.test_mojo_ir_printer import (
    test_render_struct_decl_preserves_trait_order_c97f6c2e5190,
)
from acceptance.test_mojo_ir_printer import (
    test_render_mojo_module_external_surface_with_synthesized_callback_aliases_4f0954f0f361,
)
from acceptance.test_mojo_ir_printer import (
    test_render_bitfield_accessors_branch_on_target_endianness_comptime_251306d1878f,
)
from acceptance.test_mojo_ir_printer import (
    test_render_callback_alias_uses_none_in_signature_position_43f49c2b4de9,
)
from acceptance.test_mojo_ir_printer import (
    test_render_struct_emits_flexible_tail_helpers_db64aa039fe4,
)
from acceptance.test_mojo_ir_printer import (
    test_normalize_and_render_sizeof_imports_std_sys_info_ae0f3e38d170,
)
from acceptance.test_mojo_ir_printer import (
    test_normalize_mojo_module_makes_callback_hoisting_and_imports_explicit_efeb748b5593,
)
from acceptance.test_mojo_ir_printer import (
    test_normalize_mojo_module_coalesces_seeded_and_discovered_dependencies_5d551be97f7c,
)
from acceptance.test_mojo_ir_printer import (
    test_render_mojo_module_uses_owned_dl_handle_library_path_hint_a87f41276b5e,
)
from acceptance.test_mojo_ir_printer import (
    test_render_owned_dl_handle_sanitizes_library_path_env_var_5cc3c75ca1c0,
)
from acceptance.test_mojo_ir_printer import (
    test_render_owned_dl_handle_function_local_does_not_collide_with_parameters_fe20c2bc8d04,
)
from acceptance.test_mojo_ir_printer import (
    test_render_mojo_module_emits_inline_directive_stub_comments_a4244b538689,
)
from acceptance.test_mojo_ir_printer import (
    test_normalize_mojo_module_sets_align_decorator_before_printing_87f0f66956e2,
)
from acceptance.test_mojo_ir_printer import (
    test_normalize_and_printer_keep_union_byte_fallback_without_unsafe_union_import_d2491febe2bb,
)
from acceptance.test_mojo_ir_printer import (
    test_printer_uses_explicit_align_decorator_only_f3cea8fd6a4f,
)
from acceptance.test_mojo_ir_printer import (
    test_printer_renders_lowered_struct_layout_members_without_normalize_inference_353d71fa5986,
)
from acceptance.test_mojo_ir_printer import (
    test_rendered_mojo_module_compiles_with_mixed_decl_kinds_94196c4865d6,
)
from acceptance.test_mojo_ir_printer import (
    test_rendered_docstring_comments_escape_backslashes_for_mojo_00ad0d1a0c88,
)
from acceptance.test_backend_contracts import (
    test_debug_decoder_failure_preserves_input_and_recovers_f59a496cf91d,
)
from acceptance.test_backend_contracts import (
    test_debug_decoder_failure_preserves_input_and_recovers_46d41663b373,
)
from acceptance.test_backend_contracts import (
    test_debug_decoder_failure_preserves_input_and_recovers_698bbff91783,
)
from acceptance.test_backend_contracts import (
    test_debug_decoder_failure_preserves_input_and_recovers_9a265ba472c8,
)


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    var suite = TestSuite()
    suite.test[test_map_const_expr_maps_binary_ref_cast_and_sizeof_nodes_83464734ef41]()
    suite.test[test_map_const_expr_parses_decimal_and_hex_float_literals_b18580b08584]()
    suite.test[test_map_float_numeric_edges_9989d78b8e69]()
    suite.test[test_map_float_numeric_edges_fce5e0c6f07c]()
    suite.test[test_map_float_numeric_edges_485e1e9c90f6]()
    suite.test[test_map_float_numeric_edges_54dcb952e2c1]()
    suite.test[test_map_float_numeric_edges_f02c5a7947bb]()
    suite.test[test_map_float_numeric_edges_3bd46e2f9065]()
    suite.test[test_expression_mapping_recovers_after_rejected_nullptr_41cee805a0b8]()
    suite.test[test_recursive_expression_mapping_preserves_shared_inputs_bc3bc879a0db]()
    suite.test[test_map_unit_builds_module_metadata_and_preserves_decl_order_91128f572e27]()
    suite.test[test_map_unit_uses_owned_dl_handle_module_policy_for_wrappers_06d8776fdfdb]()
    suite.test[test_map_unit_maps_typedef_and_enum_surface_forms_42e2cc8c815f]()
    suite.test[test_map_unit_maps_function_and_global_0667c0c37240]()
    suite.test[test_map_unit_stubs_inline_functions_and_preserves_attrs_446d7a42d6c4]()
    suite.test[test_map_unit_maps_const_and_supported_macro_to_aliases_244b32e3fbf7]()
    suite.test[test_map_unit_emits_placeholder_macro_when_not_parsed_5f33bd7e5256]()
    suite.test[test_map_unit_preserves_macro_with_unemitted_reference_f4a1caf46ab6]()
    suite.test[test_map_unit_preserves_macro_with_unfolded_c_logical_operator_e2223998106c]()
    suite.test[test_map_unit_maps_structs_and_unions_with_real_record_layouts_8d3e1083ade5]()
    suite.test[test_map_unit_uses_unsafe_union_for_repeated_types_union_57b9c9b66c11]()
    suite.test[test_map_unit_keeps_incomplete_union_as_placeholder_alias_90244efc9b5f]()
    suite.test[test_map_unit_maps_structs_that_store_union_members_by_named_alias_223e0ab75909]()
    suite.test[test_map_unit_keeps_raw_callback_types_inline_7dae617268bb]()
    suite.test[test_map_unit_synthesizes_aliases_for_external_typeref_uses_3ea606c9f8d9]()
    suite.test[test_map_unit_synthesizes_exact_width_stdint_aliases_as_fixed_width_fc279eb6c4a5]()
    suite.test[test_map_unit_maps_local_exact_width_typedef_and_chain_1485739115dd]()
    suite.test[test_map_unit_keeps_unrelated_unsigned_int_typedef_as_c_uint_b2c0637a95b0]()
    suite.test[test_map_unit_keeps_ordinary_long_as_c_long_e6d599bda567]()
    suite.test[test_map_unit_keeps_placeholder_const_when_const_expr_mapping_fails_9f1b146e84a4]()
    suite.test[test_generator_emits_integer_cast_macro_as_single_scalar_call_7b2f110db7e1]()
    suite.test[test_incomplete_struct_emitted_as_opaque_stub_not_as_layout_struct_56a1f1112619]()
    suite.test[test_generator_emits_pure_bitfield_struct_as_storage_plus_accessors_e240ca9cdb36]()
    suite.test[test_generator_emits_mixed_struct_bitfields_as_storage_plus_accessors_d4d8dc9baf67]()
    suite.test[test_generator_preserves_typedef_names_for_bitfield_accessors_cea1edf9efaa]()
    suite.test[
        test_generator_resets_bitfield_storage_after_zero_width_boundary_in_mixed_struct_a4acda68dadc
    ]()
    suite.test[
        test_generator_emits_zero_init_only_for_anonymous_only_pure_bitfield_struct_7582e1bd5b30
    ]()
    suite.test[test_generator_omits_self_alias_typedef_for_complete_union_name_92bbd843c055]()
    suite.test[test_generator_renders_global_var_stub_and_macro_comments_b565517c82ce]()
    suite.test[
        test_generator_emits_macro_and_const_before_global_and_function_sections_1acf8ffa4bd8
    ]()
    suite.test[test_generator_strips_c_float_suffix_in_macro_and_const_040a069b73c5]()
    suite.test[test_generator_imports_simd_complex_atomic_and_emits_fallback_notes_327514490783]()
    suite.test[test_generator_imports_atomic_for_representable_atomic_types_d465d057a24d]()
    suite.test[
        test_generator_omits_copy_traits_and_fieldwise_init_for_atomic_struct_fields_9c0190d73a25
    ]()
    suite.test[test_generator_emits_global_const_wrapper_for_const_qualified_scalar_e6fab93555cf]()
    suite.test[test_generator_preserves_typedef_names_in_fields_globals_and_aliases_5525968e9afd]()
    suite.test[
        test_generator_emits_function_pointer_return_wrappers_for_both_link_modes_85faea9ab837
    ]()
    suite.test[test_generator_emits_struct_field_callback_aliases_894d79fd3ef7]()
    suite.test[test_generator_emits_nominal_union_alias_for_struct_arm_union_63968f1bdabc]()
    suite.test[
        test_generator_emits_documented_inline_array_fallback_for_duplicated_type_union_0d8759557ca3
    ]()
    suite.test[test_generator_uses_callback_alias_types_in_wrapper_abi_lists_1a63371d7d6f]()
    suite.test[test_generator_keeps_nested_callback_typedef_in_wrapper_abi_lists_a8e54b819b45]()
    suite.test[test_generator_emits_std_ffi_c_aliases_and_imports_by_default_43f6ee810863]()
    suite.test[
        test_generator_imports_std_ffi_scalars_used_only_in_callback_signatures_e44c24105582
    ]()
    suite.test[test_collect_layout_record_checks_for_plain_struct_with_padding_95eab877197d]()
    suite.test[
        test_collect_layout_record_checks_uses_emitted_indices_after_bitfield_padding_ab3247cc497b
    ]()
    suite.test[
        test_collect_layout_record_checks_for_opaque_storage_skips_field_offsets_ac6b7d212475
    ]()
    suite.test[test_collect_layout_record_checks_for_bitfield_storage_group_offset_6fc2f0faadc4]()
    suite.test[
        test_collect_layout_record_checks_uses_emitted_indices_for_bitfield_groups_647bb25621a0
    ]()
    suite.test[
        test_collect_layout_record_checks_skips_incomplete_union_and_missing_record_decl_159553085b0c
    ]()
    suite.test[test_render_layout_test_module_imports_records_and_calls_tests_8f223049082c]()
    suite.test[test_render_struct_decl_preserves_trait_order_c97f6c2e5190]()
    suite.test[
        test_render_mojo_module_external_surface_with_synthesized_callback_aliases_4f0954f0f361
    ]()
    suite.test[test_render_bitfield_accessors_branch_on_target_endianness_comptime_251306d1878f]()
    suite.test[test_render_callback_alias_uses_none_in_signature_position_43f49c2b4de9]()
    suite.test[test_render_struct_emits_flexible_tail_helpers_db64aa039fe4]()
    suite.test[test_normalize_and_render_sizeof_imports_std_sys_info_ae0f3e38d170]()
    suite.test[
        test_normalize_mojo_module_makes_callback_hoisting_and_imports_explicit_efeb748b5593
    ]()
    suite.test[
        test_normalize_mojo_module_coalesces_seeded_and_discovered_dependencies_5d551be97f7c
    ]()
    suite.test[test_render_mojo_module_uses_owned_dl_handle_library_path_hint_a87f41276b5e]()
    suite.test[test_render_owned_dl_handle_sanitizes_library_path_env_var_5cc3c75ca1c0]()
    suite.test[
        test_render_owned_dl_handle_function_local_does_not_collide_with_parameters_fe20c2bc8d04
    ]()
    suite.test[test_render_mojo_module_emits_inline_directive_stub_comments_a4244b538689]()
    suite.test[test_normalize_mojo_module_sets_align_decorator_before_printing_87f0f66956e2]()
    suite.test[
        test_normalize_and_printer_keep_union_byte_fallback_without_unsafe_union_import_d2491febe2bb
    ]()
    suite.test[test_printer_uses_explicit_align_decorator_only_f3cea8fd6a4f]()
    suite.test[
        test_printer_renders_lowered_struct_layout_members_without_normalize_inference_353d71fa5986
    ]()
    suite.test[test_rendered_mojo_module_compiles_with_mixed_decl_kinds_94196c4865d6]()
    suite.test[test_rendered_docstring_comments_escape_backslashes_for_mojo_00ad0d1a0c88]()
    suite.test[test_debug_decoder_failure_preserves_input_and_recovers_f59a496cf91d]()
    suite.test[test_debug_decoder_failure_preserves_input_and_recovers_46d41663b373]()
    suite.test[test_debug_decoder_failure_preserves_input_and_recovers_698bbff91783]()
    suite.test[test_debug_decoder_failure_preserves_input_and_recovers_9a265ba472c8]()
    suite^.run()
