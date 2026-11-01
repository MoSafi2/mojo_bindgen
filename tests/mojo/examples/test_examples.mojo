"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_zlib_external_call() raises:
    check_case("test_examples/59e5dce947a1.json.gz")


def test_zlib_owned_dl_handle() raises:
    check_case("test_examples/79c573a92299.json.gz")


def test_cairo_external_call() raises:
    check_case("test_examples/ba09e6b34c4f.json.gz")


def test_cairo_owned_dl_handle() raises:
    check_case("test_examples/4687e3978a52.json.gz")


def test_libpng_external_call() raises:
    check_case("test_examples/2a8beb1119f9.json.gz")


def test_libpng_owned_dl_handle() raises:
    check_case("test_examples/56f34c37423e.json.gz")


def test_sqlite_external_call() raises:
    check_case("test_examples/11fd58e063c5.json.gz")


def test_sqlite_owned_dl_handle() raises:
    check_case("test_examples/4cbc6b6096e5.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
