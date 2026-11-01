"""Native CLI output exercised against C on stable Mojo at both optimizations."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_c_abi_memory_returns() raises:
    check_case("test_c_abi_returns/memory_returns.json")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
