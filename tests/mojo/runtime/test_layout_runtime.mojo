"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_layout_runtime_full_surface_runtime() raises:
    check_case("test_layout_runtime/d01475dcca73.json.gz")


def test_layout_runtime_large_alignment() raises:
    check_case("test_layout_runtime/6c4a67c63b66.json.gz")


def test_layout_runtime_zero_length_tail_access() raises:
    check_case("test_layout_runtime/6ed4d31360c5.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
