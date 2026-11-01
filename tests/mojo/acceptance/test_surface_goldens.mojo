"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_surface_fixture_external_55e3f7e57858() raises:
    check_case("test_surface_goldens/55e3f7e57858.json.gz")


def test_surface_fixture_external_d0acf541ca35() raises:
    check_case("test_surface_goldens/d0acf541ca35.json.gz")


def test_surface_fixture_external_60b7c4345ce0() raises:
    check_case("test_surface_goldens/60b7c4345ce0.json.gz")


def test_surface_fixture_external_ba46b190cd09() raises:
    check_case("test_surface_goldens/ba46b190cd09.json.gz")


def test_surface_fixture_external_db26d1e59562() raises:
    check_case("test_surface_goldens/db26d1e59562.json.gz")


def test_surface_fixture_external_e803b9da59fa() raises:
    check_case("test_surface_goldens/e803b9da59fa.json.gz")


def test_surface_fixture_external_39cb1ad905c1() raises:
    check_case("test_surface_goldens/39cb1ad905c1.json.gz")


def test_surface_fixture_external_ed337d64b1e7() raises:
    check_case("test_surface_goldens/ed337d64b1e7.json.gz")


def test_surface_fixture_external_7c155b2d6f18() raises:
    check_case("test_surface_goldens/7c155b2d6f18.json.gz")


def test_surface_fixture_external_e27e24e8a8a3() raises:
    check_case("test_surface_goldens/e27e24e8a8a3.json.gz")


def test_surface_fixture_external_07c0a2087c08() raises:
    check_case("test_surface_goldens/07c0a2087c08.json.gz")


def test_surface_fixture_external_63c75e978463() raises:
    check_case("test_surface_goldens/63c75e978463.json.gz")


def test_surface_fixture_external_135880c7bfdc() raises:
    check_case("test_surface_goldens/135880c7bfdc.json.gz")


def test_surface_fixture_external_2c49d7a8ef24() raises:
    check_case("test_surface_goldens/2c49d7a8ef24.json.gz")


def test_surface_fixture_external_5a68ae3046e9() raises:
    check_case("test_surface_goldens/5a68ae3046e9.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
