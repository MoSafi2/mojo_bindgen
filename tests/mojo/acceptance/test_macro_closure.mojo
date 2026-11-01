"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_fold_const_expr_unary_neg_int_0827881b6553() raises:
    check_case("test_macro_closure/0827881b6553.json.gz")


def test_fold_const_expr_binary_bitwise_chain_e212ee1923d3() raises:
    check_case("test_macro_closure/e212ee1923d3.json.gz")


def test_expand_object_like_respects_recursion_guard_069aece77c76() raises:
    check_case("test_macro_closure/069aece77c76.json.gz")


def test_expand_object_like_substitutes_included_name_01d7395d4fa6() raises:
    check_case("test_macro_closure/01d7395d4fa6.json.gz")


def test_macro_closure_cross_include_header_e054de7428f7() raises:
    check_case("test_macro_closure/e054de7428f7.json.gz")


def test_include_headers_emit_translation_unit_declarations_and_macros_22e134f1f6b5() raises:
    check_case("test_macro_closure/22e134f1f6b5.json.gz")


def test_empty_macros_are_pruned_from_translation_unit_4e19c47ea34b() raises:
    check_case("test_macro_closure/4e19c47ea34b.json.gz")


def test_collect_object_like_macro_env_last_wins_d7f36508d008() raises:
    check_case("test_macro_closure/d7f36508d008.json.gz")


def test_ordered_macro_values_do_not_fold_through_later_definitions_5dd55441662c() raises:
    check_case("test_macro_closure/5dd55441662c.json.gz")


def test_clang_macro_fallback_evaluates_unsupported_integer_macro_5f7de2a5802e() raises:
    check_case("test_macro_closure/5f7de2a5802e.json.gz")


def test_clang_macro_fallback_evaluates_parsed_but_unclean_macro_5684f0150a5e() raises:
    check_case("test_macro_closure/5684f0150a5e.json.gz")


def test_clang_macro_fallback_preserves_parsed_unsigned_macro_type_e5b7e23f487a() raises:
    check_case("test_macro_closure/e5b7e23f487a.json.gz")


def test_macro_env_does_not_fold_through_unemitted_compiler_macros_549a719c9102() raises:
    check_case("test_macro_closure/549a719c9102.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
