"""Fixed subsystem suite; individual files remain independently runnable."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case


from acceptance.test_type_vectors import test_every_source_family_matches_python
from acceptance.test_type_vectors import test_parsed_fixture_type_slots_match_python
from acceptance.test_type_vectors import test_target_family_roundtrips_and_rejects_wrong_stages
from acceptance.test_type_vectors import test_unicode_normalization_and_utf8_json
from acceptance.test_backend_vectors import test_all_shared_fixture_intermediates_and_exact_sources
from acceptance.test_backend_vectors import (
    test_constructed_ir_exact_values_options_and_generate_api,
)
from acceptance.test_backend_vectors import test_expressions_numeric_edges_and_failure_recovery
from acceptance.test_backend_vectors import (
    test_debug_decoders_defaults_wrong_family_and_unknown_fields,
)
from acceptance.test_backend_vectors import test_validation_errors_and_same_process_recovery
from acceptance.test_backend_vectors import (
    test_constructed_target_roundtrip_normalization_and_printer,
)
from acceptance.test_backend_vectors import (
    test_expression_debug_roundtrips_include_nonfinite_and_all_operators,
)
from acceptance.test_backend_vectors import (
    test_exact_native_constant_folding_and_invalid_operations,
)


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    var suite = TestSuite()
    suite.test[test_every_source_family_matches_python]()
    suite.test[test_parsed_fixture_type_slots_match_python]()
    suite.test[test_target_family_roundtrips_and_rejects_wrong_stages]()
    suite.test[test_unicode_normalization_and_utf8_json]()
    suite.test[test_all_shared_fixture_intermediates_and_exact_sources]()
    suite.test[test_constructed_ir_exact_values_options_and_generate_api]()
    suite.test[test_expressions_numeric_edges_and_failure_recovery]()
    suite.test[test_debug_decoders_defaults_wrong_family_and_unknown_fields]()
    suite.test[test_validation_errors_and_same_process_recovery]()
    suite.test[test_constructed_target_roundtrip_normalization_and_printer]()
    suite.test[test_expression_debug_roundtrips_include_nonfinite_and_all_operators]()
    suite.test[test_exact_native_constant_folding_and_invalid_operations]()
    suite^.run()
