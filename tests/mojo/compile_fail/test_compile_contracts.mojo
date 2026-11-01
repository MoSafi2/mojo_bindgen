"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_reject_missing_expression_case() raises:
    check_case("test_compile_contracts/31f4f035a1b3.json.gz")


def test_reject_source_child_in_target() raises:
    check_case("test_compile_contracts/9e2d3178bff8.json.gz")


def test_reject_mapping_target_as_source() raises:
    check_case("test_compile_contracts/31cd14e17fdc.json.gz")


def test_reject_missing_type_case() raises:
    check_case("test_compile_contracts/7149e483154c.json.gz")


def test_reject_source_expression_in_target() raises:
    check_case("test_compile_contracts/8823422a3326.json.gz")


def test_reject_printer_source_module() raises:
    check_case("test_compile_contracts/d3de51f60f9d.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
