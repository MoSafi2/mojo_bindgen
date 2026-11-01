"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_stress_fixture_emits_non_empty_source_4b788d03feee() raises:
    check_case("test_stress_emit/4b788d03feee.json.gz")


def test_stress_fixture_emits_non_empty_source_f06bea605089() raises:
    check_case("test_stress_emit/f06bea605089.json.gz")


def test_stress_fixture_emits_non_empty_source_75fa650043fe() raises:
    check_case("test_stress_emit/75fa650043fe.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
