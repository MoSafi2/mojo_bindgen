"""Fixed subsystem suite; individual files remain independently runnable."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case


from acceptance.test_type_lowering import (
    test_type_lowering_preserves_typedefs_by_context_dd5b6d22437e,
)
from acceptance.test_type_lowering import (
    test_type_lowering_preserves_callback_parameter_names_across_positions_18bfc5469eb3,
)
from acceptance.test_type_lowering import (
    test_decl_lowering_preserves_inline_and_noreturn_function_attrs_56a356e4c632,
)
from acceptance.test_type_lowering import (
    test_codegen_preserves_callback_parameter_names_and_falls_back_for_unnamed_bdad55f401c8,
)
from acceptance.test_type_lowering import (
    test_type_lowering_fully_canonicalizes_nested_typedef_chain_c0750d859c63,
)
from acceptance.test_type_lowering import (
    test_record_lowering_handles_nested_anon_and_bitfields_f436d7156348,
)
from acceptance.test_type_lowering import (
    test_record_lowering_preserves_typedef_backed_bitfields_1a77f97be758,
)
from acceptance.test_type_lowering import (
    test_parser_materializes_named_embedded_structs_from_included_headers_e85c30e0742b,
)
from acceptance.test_type_lowering import (
    test_record_lowering_preserves_direct_anonymous_record_members_5dc8ac389959,
)
from acceptance.test_type_lowering import (
    test_codegen_emits_synthesized_fields_for_direct_anonymous_members_7b6efde3a7b4,
)
from acceptance.test_type_lowering import (
    test_record_lowering_handles_recursive_pointer_to_self_d26ed230c7de,
)
from acceptance.test_type_lowering import (
    test_record_lowering_marks_trailing_empty_and_zero_length_fams_58b751250361,
)
from acceptance.test_type_lowering import (
    test_record_lowering_warns_for_non_trailing_fam_like_field_0f1b110002de,
)
from acceptance.test_type_lowering import (
    test_type_lowering_preserves_qualified_atomic_pointee_312d59155374,
)
from acceptance.test_type_lowering import (
    test_type_lowering_recovers_vector_lane_count_for_vector_size_typedef_b67324960495,
)
from acceptance.test_type_lowering import (
    test_record_lowering_emits_named_nested_record_defs_for_pointer_fields_1bfa46edf8c5,
)
from acceptance.test_type_lowering import (
    test_record_lowering_emits_named_nested_record_defs_for_value_fields_1ac282c65f95,
)
from acceptance.test_type_lowering import (
    test_record_lowering_reuses_named_nested_record_nominally_after_definition_356b5bd923f1,
)
from acceptance.test_type_lowering import (
    test_codegen_emits_named_nested_record_defs_before_parent_50f02f2bc518,
)
from acceptance.test_type_lowering import (
    test_type_lowering_preserves_declarations_beyond_child_limit_cf06de5084c4,
)
from acceptance.test_macro_closure import test_fold_const_expr_unary_neg_int_0827881b6553
from acceptance.test_macro_closure import test_fold_const_expr_binary_bitwise_chain_e212ee1923d3
from acceptance.test_macro_closure import (
    test_expand_object_like_respects_recursion_guard_069aece77c76,
)
from acceptance.test_macro_closure import (
    test_expand_object_like_substitutes_included_name_01d7395d4fa6,
)
from acceptance.test_macro_closure import test_macro_closure_cross_include_header_e054de7428f7
from acceptance.test_macro_closure import (
    test_include_headers_emit_translation_unit_declarations_and_macros_22e134f1f6b5,
)
from acceptance.test_macro_closure import (
    test_empty_macros_are_pruned_from_translation_unit_4e19c47ea34b,
)
from acceptance.test_macro_closure import test_collect_object_like_macro_env_last_wins_d7f36508d008
from acceptance.test_macro_closure import (
    test_ordered_macro_values_do_not_fold_through_later_definitions_5dd55441662c,
)
from acceptance.test_macro_closure import (
    test_clang_macro_fallback_evaluates_unsupported_integer_macro_5f7de2a5802e,
)
from acceptance.test_macro_closure import (
    test_clang_macro_fallback_evaluates_parsed_but_unclean_macro_5684f0150a5e,
)
from acceptance.test_macro_closure import (
    test_clang_macro_fallback_preserves_parsed_unsigned_macro_type_e5b7e23f487a,
)
from acceptance.test_macro_closure import (
    test_macro_env_does_not_fold_through_unemitted_compiler_macros_549a719c9102,
)
from acceptance.test_doc_comments import (
    test_parser_captures_docs_on_public_declarations_790c57172c12,
)
from acceptance.test_doc_comments import (
    test_mojo_emits_docs_and_respects_disable_option_8f26a51ce2ce,
)
from acceptance.test_target_abi import test_clang_parser_records_target_abi_on_unit_6a99540b9e7d
from acceptance.test_target_abi import test_unit_json_roundtrip_preserves_target_abi_f82bd657bdd2
from acceptance.test_cli_contracts import test_cli_help
from acceptance.test_cli_contracts import test_cli_version
from acceptance.test_cli_contracts import test_cli_unknown
from acceptance.test_cli_contracts import test_cli_missing
from acceptance.test_cli_contracts import test_cli_parse_error
from acceptance.test_cli_contracts import test_cli_calling_convention
from acceptance.test_cli_contracts import test_warning_exit_and_json
from acceptance.test_cli_contracts import test_cli_preprocess_public_headers
from acceptance.test_cli_contracts import test_unicode_target_host
from acceptance.test_cli_contracts import test_unicode_target_i386
from acceptance.test_cli_contracts import test_unicode_target_unsigned_char


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    var suite = TestSuite()
    suite.test[test_type_lowering_preserves_typedefs_by_context_dd5b6d22437e]()
    suite.test[
        test_type_lowering_preserves_callback_parameter_names_across_positions_18bfc5469eb3
    ]()
    suite.test[test_decl_lowering_preserves_inline_and_noreturn_function_attrs_56a356e4c632]()
    suite.test[
        test_codegen_preserves_callback_parameter_names_and_falls_back_for_unnamed_bdad55f401c8
    ]()
    suite.test[test_type_lowering_fully_canonicalizes_nested_typedef_chain_c0750d859c63]()
    suite.test[test_record_lowering_handles_nested_anon_and_bitfields_f436d7156348]()
    suite.test[test_record_lowering_preserves_typedef_backed_bitfields_1a77f97be758]()
    suite.test[test_parser_materializes_named_embedded_structs_from_included_headers_e85c30e0742b]()
    suite.test[test_record_lowering_preserves_direct_anonymous_record_members_5dc8ac389959]()
    suite.test[test_codegen_emits_synthesized_fields_for_direct_anonymous_members_7b6efde3a7b4]()
    suite.test[test_record_lowering_handles_recursive_pointer_to_self_d26ed230c7de]()
    suite.test[test_record_lowering_marks_trailing_empty_and_zero_length_fams_58b751250361]()
    suite.test[test_record_lowering_warns_for_non_trailing_fam_like_field_0f1b110002de]()
    suite.test[test_type_lowering_preserves_qualified_atomic_pointee_312d59155374]()
    suite.test[test_type_lowering_recovers_vector_lane_count_for_vector_size_typedef_b67324960495]()
    suite.test[
        test_record_lowering_emits_named_nested_record_defs_for_pointer_fields_1bfa46edf8c5
    ]()
    suite.test[test_record_lowering_emits_named_nested_record_defs_for_value_fields_1ac282c65f95]()
    suite.test[
        test_record_lowering_reuses_named_nested_record_nominally_after_definition_356b5bd923f1
    ]()
    suite.test[test_codegen_emits_named_nested_record_defs_before_parent_50f02f2bc518]()
    suite.test[test_type_lowering_preserves_declarations_beyond_child_limit_cf06de5084c4]()
    suite.test[test_fold_const_expr_unary_neg_int_0827881b6553]()
    suite.test[test_fold_const_expr_binary_bitwise_chain_e212ee1923d3]()
    suite.test[test_expand_object_like_respects_recursion_guard_069aece77c76]()
    suite.test[test_expand_object_like_substitutes_included_name_01d7395d4fa6]()
    suite.test[test_macro_closure_cross_include_header_e054de7428f7]()
    suite.test[test_include_headers_emit_translation_unit_declarations_and_macros_22e134f1f6b5]()
    suite.test[test_empty_macros_are_pruned_from_translation_unit_4e19c47ea34b]()
    suite.test[test_collect_object_like_macro_env_last_wins_d7f36508d008]()
    suite.test[test_ordered_macro_values_do_not_fold_through_later_definitions_5dd55441662c]()
    suite.test[test_clang_macro_fallback_evaluates_unsupported_integer_macro_5f7de2a5802e]()
    suite.test[test_clang_macro_fallback_evaluates_parsed_but_unclean_macro_5684f0150a5e]()
    suite.test[test_clang_macro_fallback_preserves_parsed_unsigned_macro_type_e5b7e23f487a]()
    suite.test[test_macro_env_does_not_fold_through_unemitted_compiler_macros_549a719c9102]()
    suite.test[test_parser_captures_docs_on_public_declarations_790c57172c12]()
    suite.test[test_mojo_emits_docs_and_respects_disable_option_8f26a51ce2ce]()
    suite.test[test_clang_parser_records_target_abi_on_unit_6a99540b9e7d]()
    suite.test[test_unit_json_roundtrip_preserves_target_abi_f82bd657bdd2]()
    suite.test[test_cli_help]()
    suite.test[test_cli_version]()
    suite.test[test_cli_unknown]()
    suite.test[test_cli_missing]()
    suite.test[test_cli_parse_error]()
    suite.test[test_cli_calling_convention]()
    suite.test[test_warning_exit_and_json]()
    suite.test[test_cli_preprocess_public_headers]()
    suite.test[test_unicode_target_host]()
    suite.test[test_unicode_target_i386]()
    suite.test[test_unicode_target_unsigned_char]()
    suite^.run()
