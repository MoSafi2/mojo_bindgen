from clang.cindex import Index, UnsavedFile, TranslationUnitFlags
from mojo_bindgen.parsing._compat import parse_translation_unit
from mojo_bindgen.parsing.frontend import children, tokens, collect_diagnostics
from std.testing import assert_equal, TestSuite


def test_installed_clang() raises:
    var index = Index.create()
    var tu = parse_translation_unit(
        index,
        "/tmp/mojo_bindgen_frontend_test.h",
        args=["-xc"],
        files=[
            UnsavedFile(
                "/tmp/mojo_bindgen_frontend_test.h", "struct Point { int x; };\nint add(int x);\n"
            )
        ],
    )
    var root = tu.cursor()
    var nodes = children(root)
    assert_equal(len(nodes), 2)
    assert_equal(nodes[0].spelling(), "Point")
    assert_equal(tokens(nodes[1])[0], "int")
    assert_equal(len(collect_diagnostics(tu)), 0)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
