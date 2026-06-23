# Tests for parser-derived target ABI facts on CIR units.
# Ported from tests/unit/test_target_abi.py

from std.testing import assert_true, assert_equal, TestSuite
from mojo.parsing.target_abi import probe_target_abi
from mojo.parsing.parser import ClangParser
from mojo.ir import ByteOrder

comptime _FIXTURES = "tests/mojo/parsing/fixtures"
comptime _REPO_ROOT = "/home/mmabrouk/mojo_bindgen"


def test_probe_target_abi_returns_sensible_facts() raises:
    var abi = probe_target_abi(["-x", "c", "-std=gnu11"])
    assert_true(abi.pointer_size_bytes > 0)
    assert_true(abi.pointer_align_bytes > 0)
    assert_true(abi.byte_order == ByteOrder.LITTLE or abi.byte_order == ByteOrder.BIG)


def test_clang_parser_records_target_abi_on_unit() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/probe.h"
    var unit = ClangParser(
        header=header, library="probe", link_name="probe",
        compile_args=List[String](),
    ).run()

    assert_true(unit.target_abi.pointer_size_bytes > 0)
    assert_true(unit.target_abi.pointer_align_bytes > 0)
    assert_true(
        unit.target_abi.byte_order == ByteOrder.LITTLE or
        unit.target_abi.byte_order == ByteOrder.BIG
    )


def test_unit_json_roundtrip_preserves_target_abi() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/probe_int.h"
    var unit = ClangParser(
        header=header, library="probe", link_name="probe",
        compile_args=List[String](),
    ).run()

    var json = unit.to_json()
    var restored = Unit.from_json(json)

    assert_equal(restored.target_abi.pointer_size_bytes, unit.target_abi.pointer_size_bytes)
    assert_equal(restored.target_abi.pointer_align_bytes, unit.target_abi.pointer_align_bytes)
    assert_equal(restored.target_abi.byte_order, unit.target_abi.byte_order)


from mojo.ir import Unit


def main() raises:
    var suite = TestSuite("parsing/target_abi")
    suite.run(test_probe_target_abi_returns_sensible_facts)
    suite.run(test_clang_parser_records_target_abi_on_unit)
    suite.run(test_unit_json_roundtrip_preserves_target_abi)
    suite.report()