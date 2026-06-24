# Tests for source documentation comment capture.
# Ported from tests/unit/test_doc_comments.py (the libclang-driving tests).

from std.testing import assert_true, TestSuite
from mojo.parsing.frontend import ClangFrontend, ClangFrontendConfig
from mojo.parsing.doc_comments import cursor_doc_comment
from clang.cindex import CursorKind

comptime _FIXTURES = "tests/mojo/parsing/fixtures"
comptime _REPO_ROOT = "/home/mmabrouk/mojo_bindgen"


def test_parser_captures_docs_on_struct() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/docs.h"
    var frontend = ClangFrontend(ClangFrontendConfig(
        header=header,
        compile_args=List[String](),
        include_headers=List[String](),
    ))
    var tu = frontend.parse_translation_unit()
    var cursors = frontend.iter_translation_unit_cursors(tu)

    var found_struct = False
    for cursor in cursors:
        if cursor.kind() == CursorKind.STRUCT_DECL and cursor.spelling() == "Widget":
            var doc_opt = cursor_doc_comment(cursor)
            assert_true(doc_opt is not None)
            assert_true(doc_opt.value().text.contains("documented struct"))
            found_struct = True
    assert_true(found_struct)


def test_parser_captures_docs_on_enum() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/docs.h"
    var frontend = ClangFrontend(ClangFrontendConfig(
        header=header,
        compile_args=List[String](),
        include_headers=List[String](),
    ))
    var tu = frontend.parse_translation_unit()
    var cursors = frontend.iter_translation_unit_cursors(tu)

    var found_enum = False
    for cursor in cursors:
        if cursor.kind() == CursorKind.ENUM_DECL and cursor.spelling() == "Mode":
            var doc_opt = cursor_doc_comment(cursor)
            assert_true(doc_opt is not None)
            assert_true(doc_opt.value().text.contains("Mode enum"))
            found_enum = True
    assert_true(found_enum)


def test_parser_captures_docs_on_field() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/docs.h"
    var frontend = ClangFrontend(ClangFrontendConfig(
        header=header,
        compile_args=List[String](),
        include_headers=List[String](),
    ))
    var tu = frontend.parse_translation_unit()
    var cursors = frontend.iter_translation_unit_cursors(tu)

    for cursor in cursors:
        if cursor.kind() == CursorKind.STRUCT_DECL and cursor.spelling() == "Widget":
            var children = cursor.children()
            for child in children:
                if child.kind() == CursorKind.FIELD_DECL and child.spelling() == "count":
                    var doc_opt = cursor_doc_comment(child)
                    assert_true(doc_opt is not None)
                    assert_true(doc_opt.value().text.contains("Field count"))


def test_parser_captures_docs_on_function() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/docs.h"
    var frontend = ClangFrontend(ClangFrontendConfig(
        header=header,
        compile_args=List[String](),
        include_headers=List[String](),
    ))
    var tu = frontend.parse_translation_unit()
    var cursors = frontend.iter_translation_unit_cursors(tu)

    var found_fn = False
    for cursor in cursors:
        if cursor.kind() == CursorKind.FUNCTION_DECL and cursor.spelling() == "add":
            var doc_opt = cursor_doc_comment(cursor)
            assert_true(doc_opt is not None)
            assert_true(doc_opt.value().text.contains("Adds two integers"))
            found_fn = True
    assert_true(found_fn)


def main() raises:
    var suite = TestSuite.discover_tests[__functions_in_module()]().run()