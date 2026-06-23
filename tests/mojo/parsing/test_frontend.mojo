# Tests for header path resolution and compile-arg defaults (no libclang required).
# Ported from tests/unit/test_parser_paths.py

from std.testing import assert_equal, assert_true, assert_raises, TestSuite
from std.pathlib import Path, cwd
from mojo.parsing.frontend import (
    ClangOptions, _resolve_header_path, _default_system_compile_args,
    _escape_include_path,
)
from mojo.utils import normalize_std_flag, build_c_parse_args

comptime _FIXTURES = "tests/mojo/parsing/fixtures"


def test_normalize_std_flag_accepts_legacy_forms() raises:
    assert_equal(normalize_std_flag("-std=c99"), "-std=c99")
    assert_equal(normalize_std_flag("--std=c99"), "-std=c99")
    assert_equal(normalize_std_flag("std=c99"), "-std=c99")
    assert_equal(normalize_std_flag("-I./include"), "-I./include")


def test_build_c_parse_args_uses_default_std_when_missing() raises:
    var args = build_c_parse_args(["-I./include"], default_std="-std=gnu11")
    assert_equal(args, ["-x", "c", "-std=gnu11", "-I./include"])


def test_build_c_parse_args_uses_user_std_and_normalizes() raises:
    var args = build_c_parse_args(
        ["--std=c99", "-I./include"], default_std="-std=gnu11"
    )
    assert_equal(args, ["-x", "c", "-std=c99", "-I./include"])


def test_build_c_parse_args_accepts_bare_std_equals() raises:
    var args = build_c_parse_args(
        ["std=c17", "-DVALUE=1"], default_std="-std=gnu11"
    )
    assert_equal(args, ["-x", "c", "-std=c17", "-DVALUE=1"])


def test_build_c_parse_args_does_not_duplicate_normalized_language_and_std() raises:
    var args = build_c_parse_args(
        ["-x", "c", "-std=c11", "-I./include"], default_std="-std=gnu11"
    )
    assert_equal(args, ["-x", "c", "-std=c11", "-I./include"])


def test_clang_options_normalizes_structured_flags_in_deterministic_order() raises:
    var options = ClangOptions(
        std="c23",
        target="wasm32-unknown-unknown",
        sysroot="/sdk",
        include_dirs=["include", "vendor/include"],
        defines=["FEATURE=1", "NAME"],
        undefines=["OLD"],
        raw_args=["-Wno-unused"],
    )
    var expected: List[String] = [
        "-x", "c", "-std=c23", "--target=wasm32-unknown-unknown",
        "--sysroot=/sdk", "-Iinclude", "-Ivendor/include",
        "-DFEATURE=1", "-DNAME", "-UOLD", "-Wno-unused",
    ]
    assert_equal(options.to_args(), expected)


def test_clang_options_raw_std_suppresses_default_gnu11() raises:
    var options = ClangOptions(raw_args=["--std=c99", "-DVALUE=1"])
    assert_equal(options.to_args(), ["-x", "c", "-std=c99", "-DVALUE=1"])


def test_returns_list_starting_with_usr_include() raises:
    var args = _default_system_compile_args()
    assert_true(len(args) >= 1)
    assert_equal(args[0], "-I/usr/include")


def test_absolute_path() raises:
    var repo_root = "/home/mmabrouk/mojo_bindgen"
    var p = repo_root + "/" + _FIXTURES + "/probe.h"
    var resolved = _resolve_header_path(p)
    assert_true(Path(resolved).is_file())


def test_escape_include_path_simple() raises:
    assert_equal(_escape_include_path("simple/path.h"), "simple/path.h")


def test_escape_include_path_backslash() raises:
    assert_equal(_escape_include_path("path\\with\\backslash.h"), "path\\\\with\\\\backslash.h")


def main() raises:
    var suite = TestSuite("parsing/frontend")
    suite.run(test_normalize_std_flag_accepts_legacy_forms)
    suite.run(test_build_c_parse_args_uses_default_std_when_missing)
    suite.run(test_build_c_parse_args_uses_user_std_and_normalizes)
    suite.run(test_build_c_parse_args_accepts_bare_std_equals)
    suite.run(test_build_c_parse_args_does_not_duplicate_normalized_language_and_std)
    suite.run(test_clang_options_normalizes_structured_flags_in_deterministic_order)
    suite.run(test_clang_options_raw_std_suppresses_default_gnu11)
    suite.run(test_returns_list_starting_with_usr_include)
    suite.run(test_absolute_path)
    suite.run(test_escape_include_path_simple)
    suite.run(test_escape_include_path_backslash)
    suite.report()