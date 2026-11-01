"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_stress_fixture_json_round_trip_77cac253f8c0() raises:
    check_case("test_stress_ir/77cac253f8c0.json.gz")


def test_stress_fixture_json_round_trip_9f26dbb3501c() raises:
    check_case("test_stress_ir/9f26dbb3501c.json.gz")


def test_stress_fixture_json_round_trip_0e6551fff2a0() raises:
    check_case("test_stress_ir/0e6551fff2a0.json.gz")


def test_pathological_core_preserves_selected_hard_declarations_178f05555cb8() raises:
    check_case("test_stress_ir/178f05555cb8.json.gz")


def test_pathological_macros_preserves_supported_and_unsupported_forms_9a82b2112aaa() raises:
    check_case("test_stress_ir/9a82b2112aaa.json.gz")


def test_pathological_layout_preserves_selected_layout_edges_55ba6fe62428() raises:
    check_case("test_stress_ir/55ba6fe62428.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
