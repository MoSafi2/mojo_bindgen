# Tests for parser frontend and declaration registry services.
# Ported from tests/unit/test_parsing_registry.py (3 in-scope tests).

from std.testing import assert_true, assert_equal, TestSuite
from clang.cindex import CursorKind
from mojo.parsing.frontend import ClangFrontend, ClangFrontendConfig
from mojo.parsing.registry import RecordRegistry

comptime _FIXTURES = "tests/mojo/parsing/fixtures"
comptime _REPO_ROOT = "/home/mmabrouk/mojo_bindgen"


def test_registry_unifies_forward_decl_and_definition() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/registry_forward.h"
    var frontend = ClangFrontend(ClangFrontendConfig(
        header=header,
        compile_args=List[String](),
        include_headers=List[String](),
    ))
    var tu = frontend.parse_translation_unit()
    var registry = RecordRegistry.build_from_translation_unit(tu, frontend)

    var nodes: List[Cursor] = []
    for cursor in frontend.iter_translation_unit_cursors(tu):
        if cursor.spelling() == "node":
            nodes.append(cursor)

    assert_equal(len(nodes), 2)
    var id0 = registry.decl_id_for_cursor(nodes[0])
    var id1 = registry.decl_id_for_cursor(nodes[1])
    assert_equal(id0, id1)
    assert_true(registry.is_complete_record_decl(nodes[0]))


def test_registry_synthesizes_anonymous_record_identity() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/registry_anon.h"
    var frontend = ClangFrontend(ClangFrontendConfig(
        header=header,
        compile_args=List[String](),
        include_headers=List[String](),
    ))
    var tu = frontend.parse_translation_unit()
    var registry = RecordRegistry.build_from_translation_unit(tu, frontend)

    var outer: Cursor = Cursor(tu)
    var found_outer = False
    for cursor in frontend.iter_translation_unit_cursors(tu):
        if cursor.kind() == CursorKind.STRUCT_DECL and cursor.spelling() == "outer":
            outer = cursor
            found_outer = True
            break
    assert_true(found_outer)

    var inner_field: Cursor = Cursor(tu)
    var found_field = False
    for child in outer.children():
        if child.kind() == CursorKind.FIELD_DECL and child.spelling() == "inner":
            inner_field = child
            found_field = True
            break
    assert_true(found_field)

    var field_type = inner_field.type().canonical()
    var decl_opt = field_type.declaration()
    assert_true(decl_opt is not None)
    var def_opt = decl_opt.value().definition()
    assert_true(def_opt is not None)
    var anonymous = def_opt.value()

    var decl_id = registry.decl_id_for_cursor(anonymous)
    assert_true(decl_id.byte_length() > 0)

    var naming = registry.record_naming(anonymous)
    assert_true(naming.name.startswith("outer__anon_struct_1"))
    assert_equal(naming.c_name, naming.name)
    assert_true(naming.is_anonymous)
    assert_true(not naming.name.contains("/"))
    assert_true(not naming.name.contains(":"))


from clang.cindex import Cursor


def test_registry_distinguishes_sibling_anonymous_record_definitions() raises:
    var header = _REPO_ROOT + "/" + _FIXTURES + "/registry_nested_anon.h"
    var frontend = ClangFrontend(ClangFrontendConfig(
        header=header,
        compile_args=List[String](),
        include_headers=List[String](),
    ))
    var tu = frontend.parse_translation_unit()
    var registry = RecordRegistry.build_from_translation_unit(tu, frontend)

    var outer: Cursor = Cursor(tu)
    var found_outer = False
    for cursor in frontend.iter_translation_unit_cursors(tu):
        if cursor.kind() == CursorKind.STRUCT_DECL and cursor.spelling() == "outer":
            outer = cursor
            found_outer = True
            break
    assert_true(found_outer)

    var anon_union: Cursor = Cursor(tu)
    var found_union = False
    for child in outer.children():
        if child.kind() == CursorKind.UNION_DECL and child.is_definition():
            anon_union = child
            found_union = True
            break
    assert_true(found_union)

    var anon_structs: List[Cursor] = []
    for child in anon_union.children():
        if child.kind() == CursorKind.STRUCT_DECL and child.is_definition():
            anon_structs.append(child)

    assert_equal(len(anon_structs), 2)

    var usr0 = anon_structs[0].usr()
    var usr1 = anon_structs[1].usr()
    assert_true(usr0 is not None)
    assert_true(usr1 is not None)
    assert_equal(usr0.value(), usr1.value())

    var id0 = registry.decl_id_for_cursor(anon_structs[0])
    var id1 = registry.decl_id_for_cursor(anon_structs[1])
    assert_true(id0 != id1)


def main() raises:
    var suite = TestSuite("parsing/registry")
    suite.run(test_registry_unifies_forward_decl_and_definition)
    suite.run(test_registry_synthesizes_anonymous_record_identity)
    suite.run(test_registry_distinguishes_sibling_anonymous_record_definitions)
    suite.report()