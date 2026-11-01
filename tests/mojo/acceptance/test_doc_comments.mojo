"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_parser_captures_docs_on_public_declarations_790c57172c12() raises:
    check_case("test_doc_comments/790c57172c12.json.gz")


def test_mojo_emits_docs_and_respects_disable_option_8f26a51ce2ce() raises:
    check_case("test_doc_comments/8f26a51ce2ce.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
