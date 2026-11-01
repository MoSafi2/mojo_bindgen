"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_all_shared_fixture_intermediates_and_exact_sources() raises:
    check_case("test_backend_vectors/ffa5f9cdb887.json.gz")


def test_constructed_ir_exact_values_options_and_generate_api() raises:
    check_case("test_backend_vectors/188454d82967.json.gz")


def test_expressions_numeric_edges_and_failure_recovery() raises:
    check_case("test_backend_vectors/71bf463a5179.json.gz")


def test_debug_decoders_defaults_wrong_family_and_unknown_fields() raises:
    check_case("test_backend_vectors/8ca683d850f9.json.gz")


def test_validation_errors_and_same_process_recovery() raises:
    check_case("test_backend_vectors/fa04eb7cb721.json.gz")


def test_constructed_target_roundtrip_normalization_and_printer() raises:
    check_case("test_backend_vectors/7218b42a5e5d.json.gz")


def test_expression_debug_roundtrips_include_nonfinite_and_all_operators() raises:
    check_case("test_backend_vectors/f8437a318507.json.gz")


def test_exact_native_constant_folding_and_invalid_operations() raises:
    check_case("test_backend_vectors/cd551e8363d2.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
