from clang.cindex import Index, UnsavedFile
from mojo_bindgen.parsing.registry import RecordRegistry, RecordState
from mojo_bindgen.parsing._identity import sha256_prefix
from mojo_bindgen.ir import Struct
from std.testing import assert_equal, assert_true, TestSuite


def test_identity_and_registry_rollback() raises:
    assert_equal(sha256_prefix("abc"), "ba7816bf8f01cfea")
    var index = Index.create()
    var tu = index.parse("registry.h", [], [UnsavedFile("registry.h", "struct Node;\n")])
    var root = tu.cursor()
    var registry = RecordRegistry(root)
    var header = Struct("node", "Node", "Node", [], 0, 1, is_complete=False)
    registry.states["node"] = RecordState.declared(header.copy())
    var prior = registry.begin(header)
    header.name = "changed builder"
    assert_equal(registry.states["node"].header().name, "Node")
    registry.abort("node", prior)
    match registry.states["node"]:
        case .declared(v):
            assert_equal(v.name, "Node")
        case _:
            raise Error("rollback did not restore declaration")
    var next = registry.begin(header)
    var finished = header.copy()
    finished.is_complete = True
    registry.publish(finished)
    finished.name = "another builder change"
    assert_equal(registry.states["node"].header().name, "changed builder")


def test_checked_children_does_not_truncate() raises:
    var source = String()
    for i in range(4100):
        source += "int variable_" + String(i) + ";\n"
    var index = Index.create()
    var tu = index.parse("overflow.h", [], [UnsavedFile("overflow.h", source^)])
    var root = tu.cursor()
    var nodes = root.children()
    assert_equal(len(nodes), 4100)
    assert_equal(nodes[0].spelling(), "variable_0")
    assert_equal(nodes[4099].spelling(), "variable_4099")
    var registry = RecordRegistry(root)
    assert_equal(len(registry.top_level), 4100)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
