"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_alignment_fixture_external_goldens_580a3dcb6a04() raises:
    check_case("test_alignment_goldens/580a3dcb6a04.json.gz")


def test_alignment_fixture_external_goldens_d66b44f9ac77() raises:
    check_case("test_alignment_goldens/d66b44f9ac77.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
