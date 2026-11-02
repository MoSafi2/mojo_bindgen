"""Fixed subsystem suite; individual files remain independently runnable."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case


from runtime.test_e2e_runtime import test_golden_runtime_case_bb53c84b8e55
from runtime.test_e2e_runtime import test_golden_runtime_case_c5f400a92861
from runtime.test_e2e_runtime import test_golden_runtime_case_1787d826609b
from runtime.test_e2e_runtime import test_golden_runtime_case_1d7066d83f79
from runtime.test_e2e_runtime import test_golden_runtime_case_aa8a2cebee24
from runtime.test_e2e_runtime import test_golden_runtime_case_3a1e3d45424f
from runtime.test_e2e_runtime import test_golden_runtime_case_da9d5607963c
from runtime.test_e2e_runtime import test_golden_runtime_case_30890e6fff2e
from runtime.test_e2e_runtime import test_golden_runtime_case_3767c59b41cf
from runtime.test_e2e_runtime import test_golden_runtime_case_eb246d0a82a2
from runtime.test_e2e_runtime import test_golden_runtime_case_bd3ce1acc22e
from runtime.test_e2e_runtime import test_golden_runtime_case_1a34a4cca7e4
from runtime.test_e2e_runtime import test_golden_runtime_case_c72018a09db3
from runtime.test_e2e_runtime import test_golden_runtime_case_9f72b1e09094
from runtime.test_e2e_runtime import test_golden_runtime_case_fa04bb2ad777
from runtime.test_mojo_12 import test_checked_varargs_and_overaligned_array_bc162a853174
from runtime.test_mojo_12 import test_varargs_reject_unsafe_arguments_b161d7969fdb
from runtime.test_mojo_12 import test_varargs_reject_unsafe_arguments_2b0d1c0f1e03
from runtime.test_mojo_12 import test_varargs_reject_unsafe_arguments_b8b0b96ed493
from runtime.test_mojo_12 import test_varargs_reject_unsafe_arguments_81009faf1a93
from runtime.test_mojo_12 import test_varargs_reject_unsafe_arguments_955fda263eb2
from runtime.test_mojo_12 import test_varargs_reject_unsafe_arguments_8463afa558fb
from runtime.test_mojo_12 import test_varargs_reject_unsafe_arguments_81dbfd031ef3
from runtime.test_mojo_12 import test_dynamic_globals_and_override_precedence_5bea586e7394
from runtime.test_mojo_12 import (
    test_missing_dynamic_symbol_keeps_non_raising_diagnostic_d28ab08e3b46,
)
from runtime.test_mojo_12 import test_missing_library_has_candidate_diagnostic_9f46869db373
from runtime.test_layout_runtime import test_layout_runtime_full_surface_runtime
from runtime.test_layout_runtime import test_layout_runtime_large_alignment
from runtime.test_layout_runtime import test_layout_runtime_zero_length_tail_access
from runtime.test_opaque_storage import test_opaque_storage_runtime
from runtime.test_c_abi_returns import test_c_abi_memory_returns


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    var suite = TestSuite()
    suite.test[test_golden_runtime_case_bb53c84b8e55]()
    suite.test[test_golden_runtime_case_c5f400a92861]()
    suite.test[test_golden_runtime_case_1787d826609b]()
    suite.test[test_golden_runtime_case_1d7066d83f79]()
    suite.test[test_golden_runtime_case_aa8a2cebee24]()
    suite.test[test_golden_runtime_case_3a1e3d45424f]()
    suite.test[test_golden_runtime_case_da9d5607963c]()
    suite.test[test_golden_runtime_case_30890e6fff2e]()
    suite.test[test_golden_runtime_case_3767c59b41cf]()
    suite.test[test_golden_runtime_case_eb246d0a82a2]()
    suite.test[test_golden_runtime_case_bd3ce1acc22e]()
    suite.test[test_golden_runtime_case_1a34a4cca7e4]()
    suite.test[test_golden_runtime_case_c72018a09db3]()
    suite.test[test_golden_runtime_case_9f72b1e09094]()
    suite.test[test_golden_runtime_case_fa04bb2ad777]()
    suite.test[test_checked_varargs_and_overaligned_array_bc162a853174]()
    suite.test[test_varargs_reject_unsafe_arguments_b161d7969fdb]()
    suite.test[test_varargs_reject_unsafe_arguments_2b0d1c0f1e03]()
    suite.test[test_varargs_reject_unsafe_arguments_b8b0b96ed493]()
    suite.test[test_varargs_reject_unsafe_arguments_81009faf1a93]()
    suite.test[test_varargs_reject_unsafe_arguments_955fda263eb2]()
    suite.test[test_varargs_reject_unsafe_arguments_8463afa558fb]()
    suite.test[test_varargs_reject_unsafe_arguments_81dbfd031ef3]()
    suite.test[test_dynamic_globals_and_override_precedence_5bea586e7394]()
    suite.test[test_missing_dynamic_symbol_keeps_non_raising_diagnostic_d28ab08e3b46]()
    suite.test[test_missing_library_has_candidate_diagnostic_9f46869db373]()
    suite.test[test_layout_runtime_full_surface_runtime]()
    suite.test[test_layout_runtime_large_alignment]()
    suite.test[test_layout_runtime_zero_length_tail_access]()
    suite.test[test_c_abi_memory_returns]()
    suite.test[test_opaque_storage_runtime]()
    suite^.run()
