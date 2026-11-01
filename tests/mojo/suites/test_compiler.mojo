"""Fixed subsystem suite; individual files remain independently runnable."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case


from compile_fail.test_compile_contracts import test_reject_missing_expression_case
from compile_fail.test_compile_contracts import test_reject_source_child_in_target
from compile_fail.test_compile_contracts import test_reject_mapping_target_as_source
from compile_fail.test_compile_contracts import test_reject_missing_type_case
from compile_fail.test_compile_contracts import test_reject_source_expression_in_target
from compile_fail.test_compile_contracts import test_reject_printer_source_module


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    var suite = TestSuite()
    suite.test[test_reject_missing_expression_case]()
    suite.test[test_reject_source_child_in_target]()
    suite.test[test_reject_mapping_target_as_source]()
    suite.test[test_reject_missing_type_case]()
    suite.test[test_reject_source_expression_in_target]()
    suite.test[test_reject_printer_source_module]()
    suite^.run()
