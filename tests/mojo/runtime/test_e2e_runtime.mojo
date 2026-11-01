"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_golden_runtime_case_bb53c84b8e55() raises:
    check_case("test_e2e_runtime/bb53c84b8e55.json.gz")


def test_golden_runtime_case_c5f400a92861() raises:
    check_case("test_e2e_runtime/c5f400a92861.json.gz")


def test_golden_runtime_case_1787d826609b() raises:
    check_case("test_e2e_runtime/1787d826609b.json.gz")


def test_golden_runtime_case_1d7066d83f79() raises:
    check_case("test_e2e_runtime/1d7066d83f79.json.gz")


def test_golden_runtime_case_aa8a2cebee24() raises:
    check_case("test_e2e_runtime/aa8a2cebee24.json.gz")


def test_golden_runtime_case_3a1e3d45424f() raises:
    check_case("test_e2e_runtime/3a1e3d45424f.json.gz")


def test_golden_runtime_case_da9d5607963c() raises:
    check_case("test_e2e_runtime/da9d5607963c.json.gz")


def test_golden_runtime_case_30890e6fff2e() raises:
    check_case("test_e2e_runtime/30890e6fff2e.json.gz")


def test_golden_runtime_case_3767c59b41cf() raises:
    check_case("test_e2e_runtime/3767c59b41cf.json.gz")


def test_golden_runtime_case_eb246d0a82a2() raises:
    check_case("test_e2e_runtime/eb246d0a82a2.json.gz")


def test_golden_runtime_case_bd3ce1acc22e() raises:
    check_case("test_e2e_runtime/bd3ce1acc22e.json.gz")


def test_golden_runtime_case_1a34a4cca7e4() raises:
    check_case("test_e2e_runtime/1a34a4cca7e4.json.gz")


def test_golden_runtime_case_c72018a09db3() raises:
    check_case("test_e2e_runtime/c72018a09db3.json.gz")


def test_golden_runtime_case_9f72b1e09094() raises:
    check_case("test_e2e_runtime/9f72b1e09094.json.gz")


def test_golden_runtime_case_fa04bb2ad777() raises:
    check_case("test_e2e_runtime/fa04bb2ad777.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
