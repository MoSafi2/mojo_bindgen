"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_debug_decoder_failure_preserves_input_and_recovers_f59a496cf91d() raises:
    check_case("test_backend_contracts/f59a496cf91d.json.gz")


def test_debug_decoder_failure_preserves_input_and_recovers_46d41663b373() raises:
    check_case("test_backend_contracts/46d41663b373.json.gz")


def test_debug_decoder_failure_preserves_input_and_recovers_698bbff91783() raises:
    check_case("test_backend_contracts/698bbff91783.json.gz")


def test_debug_decoder_failure_preserves_input_and_recovers_9a265ba472c8() raises:
    check_case("test_backend_contracts/9a265ba472c8.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
