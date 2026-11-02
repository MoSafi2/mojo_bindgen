"""C-backed storage, stride and ABI checks, independent of Python generation."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_opaque_storage_runtime() raises:
    check_case("test_opaque_storage_runtime/storage.json")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
