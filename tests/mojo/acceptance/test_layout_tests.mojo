"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_collect_layout_record_checks_for_plain_struct_with_padding_95eab877197d() raises:
    check_case("test_layout_tests/95eab877197d.json.gz")


def test_collect_layout_record_checks_uses_emitted_indices_after_bitfield_padding_ab3247cc497b() raises:
    check_case("test_layout_tests/ab3247cc497b.json.gz")


def test_collect_layout_record_checks_for_opaque_storage_skips_field_offsets_ac6b7d212475() raises:
    check_case("test_layout_tests/ac6b7d212475.json.gz")


def test_collect_layout_record_checks_for_bitfield_storage_group_offset_6fc2f0faadc4() raises:
    check_case("test_layout_tests/6fc2f0faadc4.json.gz")


def test_collect_layout_record_checks_uses_emitted_indices_for_bitfield_groups_647bb25621a0() raises:
    check_case("test_layout_tests/647bb25621a0.json.gz")


def test_collect_layout_record_checks_skips_incomplete_union_and_missing_record_decl_159553085b0c() raises:
    check_case("test_layout_tests/159553085b0c.json.gz")


def test_render_layout_test_module_imports_records_and_calls_tests_8f223049082c() raises:
    check_case("test_layout_tests/8f223049082c.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
