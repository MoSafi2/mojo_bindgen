"""Fixed subsystem suite; individual files remain independently runnable."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case


from acceptance.test_alignment_goldens import test_alignment_fixture_external_goldens_580a3dcb6a04
from acceptance.test_alignment_goldens import test_alignment_fixture_external_goldens_d66b44f9ac77
from acceptance.test_surface_goldens import test_surface_fixture_external_55e3f7e57858
from acceptance.test_surface_goldens import test_surface_fixture_external_d0acf541ca35
from acceptance.test_surface_goldens import test_surface_fixture_external_60b7c4345ce0
from acceptance.test_surface_goldens import test_surface_fixture_external_ba46b190cd09
from acceptance.test_surface_goldens import test_surface_fixture_external_db26d1e59562
from acceptance.test_surface_goldens import test_surface_fixture_external_e803b9da59fa
from acceptance.test_surface_goldens import test_surface_fixture_external_39cb1ad905c1
from acceptance.test_surface_goldens import test_surface_fixture_external_ed337d64b1e7
from acceptance.test_surface_goldens import test_surface_fixture_external_7c155b2d6f18
from acceptance.test_surface_goldens import test_surface_fixture_external_e27e24e8a8a3
from acceptance.test_surface_goldens import test_surface_fixture_external_07c0a2087c08
from acceptance.test_surface_goldens import test_surface_fixture_external_63c75e978463
from acceptance.test_surface_goldens import test_surface_fixture_external_135880c7bfdc
from acceptance.test_surface_goldens import test_surface_fixture_external_2c49d7a8ef24
from acceptance.test_surface_goldens import test_surface_fixture_external_5a68ae3046e9
from acceptance.test_header_corpus import test_header_corpus_case_09b0a02a2403
from acceptance.test_header_corpus import test_header_corpus_case_33eef68da406
from acceptance.test_header_corpus import test_header_corpus_case_71dab7f16477
from acceptance.test_header_corpus import test_header_corpus_case_8307eef6464a
from acceptance.test_header_corpus import test_header_corpus_case_d3e29f7a99b6
from acceptance.test_header_corpus import test_header_corpus_case_f825bd7dfb00
from acceptance.test_header_corpus import test_header_corpus_case_eaca7f2ec9eb
from acceptance.test_header_corpus import test_header_corpus_case_1603029dd5fc
from acceptance.test_header_corpus import test_header_corpus_case_aeb8bd6f745f
from acceptance.test_header_corpus import test_header_corpus_case_7e8ff4e157a5
from acceptance.test_header_corpus import test_header_corpus_case_e63b890d8f34
from acceptance.test_header_corpus import test_header_corpus_case_a964b7702d8a
from acceptance.test_header_corpus import test_header_corpus_case_7479c5ef54fb
from acceptance.test_header_corpus import test_header_corpus_case_c9e39aaf0e6f
from acceptance.test_stress_emit import test_stress_fixture_emits_non_empty_source_4b788d03feee
from acceptance.test_stress_emit import test_stress_fixture_emits_non_empty_source_f06bea605089
from acceptance.test_stress_emit import test_stress_fixture_emits_non_empty_source_75fa650043fe
from acceptance.test_stress_ir import test_stress_fixture_json_round_trip_77cac253f8c0
from acceptance.test_stress_ir import test_stress_fixture_json_round_trip_9f26dbb3501c
from acceptance.test_stress_ir import test_stress_fixture_json_round_trip_0e6551fff2a0
from acceptance.test_stress_ir import (
    test_pathological_core_preserves_selected_hard_declarations_178f05555cb8,
)
from acceptance.test_stress_ir import (
    test_pathological_macros_preserves_supported_and_unsupported_forms_9a82b2112aaa,
)
from acceptance.test_stress_ir import (
    test_pathological_layout_preserves_selected_layout_edges_55ba6fe62428,
)


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    var suite = TestSuite()
    suite.test[test_alignment_fixture_external_goldens_580a3dcb6a04]()
    suite.test[test_alignment_fixture_external_goldens_d66b44f9ac77]()
    suite.test[test_surface_fixture_external_55e3f7e57858]()
    suite.test[test_surface_fixture_external_d0acf541ca35]()
    suite.test[test_surface_fixture_external_60b7c4345ce0]()
    suite.test[test_surface_fixture_external_ba46b190cd09]()
    suite.test[test_surface_fixture_external_db26d1e59562]()
    suite.test[test_surface_fixture_external_e803b9da59fa]()
    suite.test[test_surface_fixture_external_39cb1ad905c1]()
    suite.test[test_surface_fixture_external_ed337d64b1e7]()
    suite.test[test_surface_fixture_external_7c155b2d6f18]()
    suite.test[test_surface_fixture_external_e27e24e8a8a3]()
    suite.test[test_surface_fixture_external_07c0a2087c08]()
    suite.test[test_surface_fixture_external_63c75e978463]()
    suite.test[test_surface_fixture_external_135880c7bfdc]()
    suite.test[test_surface_fixture_external_2c49d7a8ef24]()
    suite.test[test_surface_fixture_external_5a68ae3046e9]()
    suite.test[test_header_corpus_case_09b0a02a2403]()
    suite.test[test_header_corpus_case_33eef68da406]()
    suite.test[test_header_corpus_case_71dab7f16477]()
    suite.test[test_header_corpus_case_8307eef6464a]()
    suite.test[test_header_corpus_case_d3e29f7a99b6]()
    suite.test[test_header_corpus_case_f825bd7dfb00]()
    suite.test[test_header_corpus_case_eaca7f2ec9eb]()
    suite.test[test_header_corpus_case_1603029dd5fc]()
    suite.test[test_header_corpus_case_aeb8bd6f745f]()
    suite.test[test_header_corpus_case_7e8ff4e157a5]()
    suite.test[test_header_corpus_case_e63b890d8f34]()
    suite.test[test_header_corpus_case_a964b7702d8a]()
    suite.test[test_header_corpus_case_7479c5ef54fb]()
    suite.test[test_header_corpus_case_c9e39aaf0e6f]()
    suite.test[test_stress_fixture_emits_non_empty_source_4b788d03feee]()
    suite.test[test_stress_fixture_emits_non_empty_source_f06bea605089]()
    suite.test[test_stress_fixture_emits_non_empty_source_75fa650043fe]()
    suite.test[test_stress_fixture_json_round_trip_77cac253f8c0]()
    suite.test[test_stress_fixture_json_round_trip_9f26dbb3501c]()
    suite.test[test_stress_fixture_json_round_trip_0e6551fff2a0]()
    suite.test[test_pathological_core_preserves_selected_hard_declarations_178f05555cb8]()
    suite.test[test_pathological_macros_preserves_supported_and_unsupported_forms_9a82b2112aaa]()
    suite.test[test_pathological_layout_preserves_selected_layout_edges_55ba6fe62428]()
    suite^.run()
