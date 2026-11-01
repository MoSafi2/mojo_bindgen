"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_map_const_expr_maps_binary_ref_cast_and_sizeof_nodes_83464734ef41() raises:
    check_case("test_analysis_const_mapping/83464734ef41.json.gz")


def test_map_const_expr_parses_decimal_and_hex_float_literals_b18580b08584() raises:
    check_case("test_analysis_const_mapping/b18580b08584.json.gz")


def test_map_float_numeric_edges_9989d78b8e69() raises:
    check_case("test_analysis_const_mapping/9989d78b8e69.json.gz")


def test_map_float_numeric_edges_fce5e0c6f07c() raises:
    check_case("test_analysis_const_mapping/fce5e0c6f07c.json.gz")


def test_map_float_numeric_edges_485e1e9c90f6() raises:
    check_case("test_analysis_const_mapping/485e1e9c90f6.json.gz")


def test_map_float_numeric_edges_54dcb952e2c1() raises:
    check_case("test_analysis_const_mapping/54dcb952e2c1.json.gz")


def test_map_float_numeric_edges_f02c5a7947bb() raises:
    check_case("test_analysis_const_mapping/f02c5a7947bb.json.gz")


def test_map_float_numeric_edges_3bd46e2f9065() raises:
    check_case("test_analysis_const_mapping/3bd46e2f9065.json.gz")


def test_expression_mapping_recovers_after_rejected_nullptr_41cee805a0b8() raises:
    check_case("test_analysis_const_mapping/41cee805a0b8.json.gz")


def test_recursive_expression_mapping_preserves_shared_inputs_bc3bc879a0db() raises:
    check_case("test_analysis_const_mapping/bc3bc879a0db.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
