"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_every_source_family_matches_python() raises:
    check_case("test_type_vectors/2e950a668626.json.gz")


def test_parsed_fixture_type_slots_match_python() raises:
    check_case("test_type_vectors/c92b23446e1b.json.gz")


def test_target_family_roundtrips_and_rejects_wrong_stages() raises:
    check_case("test_type_vectors/b15846d8ffd6.json.gz")


def test_unicode_normalization_and_utf8_json() raises:
    check_case("test_type_vectors/a3eb9cdd9f37.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
