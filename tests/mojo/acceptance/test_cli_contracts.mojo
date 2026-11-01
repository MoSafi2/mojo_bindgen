"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_cli_help() raises:
    check_case("test_cli_contracts/e8761671cbf0.json.gz")


def test_cli_version() raises:
    check_case("test_cli_contracts/e8b21075406a.json.gz")


def test_cli_unknown() raises:
    check_case("test_cli_contracts/5973cef6f9a6.json.gz")


def test_cli_missing() raises:
    check_case("test_cli_contracts/7dd243f0a8c7.json.gz")


def test_cli_parse_error() raises:
    check_case("test_cli_contracts/7af2afeb6497.json.gz")


def test_cli_calling_convention() raises:
    check_case("test_cli_contracts/54694d4fd4b1.json.gz")


def test_warning_exit_and_json() raises:
    check_case("test_cli_contracts/f2497658bcc5.json.gz")


def test_cli_preprocess_public_headers() raises:
    check_case("test_cli_contracts/892300036bfc.json.gz")


def test_unicode_target_host() raises:
    check_case("test_cli_contracts/dc63a4c61859.json.gz")


def test_unicode_target_i386() raises:
    check_case("test_cli_contracts/a872cbf06507.json.gz")


def test_unicode_target_unsigned_char() raises:
    check_case("test_cli_contracts/7c49065cfdb8.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
