"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_checked_varargs_and_overaligned_array_bc162a853174() raises:
    check_case("test_mojo_12/bc162a853174.json.gz")


def test_varargs_reject_unsafe_arguments_b161d7969fdb() raises:
    check_case("test_mojo_12/b161d7969fdb.json.gz")


def test_varargs_reject_unsafe_arguments_2b0d1c0f1e03() raises:
    check_case("test_mojo_12/2b0d1c0f1e03.json.gz")


def test_varargs_reject_unsafe_arguments_b8b0b96ed493() raises:
    check_case("test_mojo_12/b8b0b96ed493.json.gz")


def test_varargs_reject_unsafe_arguments_81009faf1a93() raises:
    check_case("test_mojo_12/81009faf1a93.json.gz")


def test_varargs_reject_unsafe_arguments_955fda263eb2() raises:
    check_case("test_mojo_12/955fda263eb2.json.gz")


def test_varargs_reject_unsafe_arguments_8463afa558fb() raises:
    check_case("test_mojo_12/8463afa558fb.json.gz")


def test_varargs_reject_unsafe_arguments_81dbfd031ef3() raises:
    check_case("test_mojo_12/81dbfd031ef3.json.gz")


def test_dynamic_globals_and_override_precedence_5bea586e7394() raises:
    check_case("test_mojo_12/5bea586e7394.json.gz")


def test_missing_dynamic_symbol_keeps_non_raising_diagnostic_d28ab08e3b46() raises:
    check_case("test_mojo_12/d28ab08e3b46.json.gz")


def test_missing_library_has_candidate_diagnostic_9f46869db373() raises:
    check_case("test_mojo_12/9f46869db373.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
