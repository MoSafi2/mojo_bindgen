"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_type_lowering_preserves_typedefs_by_context_dd5b6d22437e() raises:
    check_case("test_type_lowering/dd5b6d22437e.json.gz")


def test_type_lowering_preserves_callback_parameter_names_across_positions_18bfc5469eb3() raises:
    check_case("test_type_lowering/18bfc5469eb3.json.gz")


def test_decl_lowering_preserves_inline_and_noreturn_function_attrs_56a356e4c632() raises:
    check_case("test_type_lowering/56a356e4c632.json.gz")


def test_codegen_preserves_callback_parameter_names_and_falls_back_for_unnamed_bdad55f401c8() raises:
    check_case("test_type_lowering/bdad55f401c8.json.gz")


def test_type_lowering_fully_canonicalizes_nested_typedef_chain_c0750d859c63() raises:
    check_case("test_type_lowering/c0750d859c63.json.gz")


def test_record_lowering_handles_nested_anon_and_bitfields_f436d7156348() raises:
    check_case("test_type_lowering/f436d7156348.json.gz")


def test_record_lowering_preserves_typedef_backed_bitfields_1a77f97be758() raises:
    check_case("test_type_lowering/1a77f97be758.json.gz")


def test_parser_materializes_named_embedded_structs_from_included_headers_e85c30e0742b() raises:
    check_case("test_type_lowering/e85c30e0742b.json.gz")


def test_record_lowering_preserves_direct_anonymous_record_members_5dc8ac389959() raises:
    check_case("test_type_lowering/5dc8ac389959.json.gz")


def test_codegen_emits_synthesized_fields_for_direct_anonymous_members_7b6efde3a7b4() raises:
    check_case("test_type_lowering/7b6efde3a7b4.json.gz")


def test_record_lowering_handles_recursive_pointer_to_self_d26ed230c7de() raises:
    check_case("test_type_lowering/d26ed230c7de.json.gz")


def test_record_lowering_marks_trailing_empty_and_zero_length_fams_58b751250361() raises:
    check_case("test_type_lowering/58b751250361.json.gz")


def test_record_lowering_warns_for_non_trailing_fam_like_field_0f1b110002de() raises:
    check_case("test_type_lowering/0f1b110002de.json.gz")


def test_type_lowering_preserves_qualified_atomic_pointee_312d59155374() raises:
    check_case("test_type_lowering/312d59155374.json.gz")


def test_type_lowering_recovers_vector_lane_count_for_vector_size_typedef_b67324960495() raises:
    check_case("test_type_lowering/b67324960495.json.gz")


def test_record_lowering_emits_named_nested_record_defs_for_pointer_fields_1bfa46edf8c5() raises:
    check_case("test_type_lowering/1bfa46edf8c5.json.gz")


def test_record_lowering_emits_named_nested_record_defs_for_value_fields_1ac282c65f95() raises:
    check_case("test_type_lowering/1ac282c65f95.json.gz")


def test_record_lowering_reuses_named_nested_record_nominally_after_definition_356b5bd923f1() raises:
    check_case("test_type_lowering/356b5bd923f1.json.gz")


def test_codegen_emits_named_nested_record_defs_before_parent_50f02f2bc518() raises:
    check_case("test_type_lowering/50f02f2bc518.json.gz")


def test_type_lowering_preserves_declarations_beyond_child_limit_cf06de5084c4() raises:
    check_case("test_type_lowering/cf06de5084c4.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
