"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_clang_parser_records_target_abi_on_unit_6a99540b9e7d() raises:
    check_case("test_target_abi/6a99540b9e7d.json.gz")


def test_unit_json_roundtrip_preserves_target_abi_f82bd657bdd2() raises:
    check_case("test_target_abi/f82bd657bdd2.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
