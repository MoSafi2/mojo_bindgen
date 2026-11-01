"""Independent native acceptance; reference provenance is in fixtures/inventory.json."""
from std.sys import argv
from std.testing import TestSuite
from reference import prepare_case, check_case


def test_header_corpus_case_09b0a02a2403() raises:
    check_case("test_header_corpus/09b0a02a2403.json.gz")


def test_header_corpus_case_33eef68da406() raises:
    check_case("test_header_corpus/33eef68da406.json.gz")


def test_header_corpus_case_71dab7f16477() raises:
    check_case("test_header_corpus/71dab7f16477.json.gz")


def test_header_corpus_case_8307eef6464a() raises:
    check_case("test_header_corpus/8307eef6464a.json.gz")


def test_header_corpus_case_d3e29f7a99b6() raises:
    check_case("test_header_corpus/d3e29f7a99b6.json.gz")


def test_header_corpus_case_f825bd7dfb00() raises:
    check_case("test_header_corpus/f825bd7dfb00.json.gz")


def test_header_corpus_case_eaca7f2ec9eb() raises:
    check_case("test_header_corpus/eaca7f2ec9eb.json.gz")


def test_header_corpus_case_1603029dd5fc() raises:
    check_case("test_header_corpus/1603029dd5fc.json.gz")


def test_header_corpus_case_aeb8bd6f745f() raises:
    check_case("test_header_corpus/aeb8bd6f745f.json.gz")


def test_header_corpus_case_7e8ff4e157a5() raises:
    check_case("test_header_corpus/7e8ff4e157a5.json.gz")


def test_header_corpus_case_e63b890d8f34() raises:
    check_case("test_header_corpus/e63b890d8f34.json.gz")


def test_header_corpus_case_a964b7702d8a() raises:
    check_case("test_header_corpus/a964b7702d8a.json.gz")


def test_header_corpus_case_7479c5ef54fb() raises:
    check_case("test_header_corpus/7479c5ef54fb.json.gz")


def test_header_corpus_case_c9e39aaf0e6f() raises:
    check_case("test_header_corpus/c9e39aaf0e6f.json.gz")


def main() raises:
    var args = argv()
    if len(args) > 1 and args[1] == "--prepare":
        prepare_case(args[2])
        return
    TestSuite.discover_tests[__functions_in_module()]().run()
