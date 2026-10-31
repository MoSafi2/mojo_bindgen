"""Recursive ownership, mapping purity, validation and recovery contracts."""

from std.memory import ArcPointer, OwnedPointer
from std.testing import assert_equal, assert_true, assert_false, assert_raises, TestSuite
from mojo_bindgen.ir import *
from mojo_bindgen.serde import dumps_c_type, dumps_mojo_type, loads_c_type, loads_mojo_type
from mojo_bindgen.type_mapping import MapTypePass, TargetQueries, validate_type_tree
from mojo_bindgen._debug_json import parse_json, dump_json
from mojo_bindgen.names import normalized_name, mojo_ident


def _mapper(var triple: Optional[String] = {}) -> MapTypePass:
    return MapTypePass(TargetQueries(TargetABI(8, 8, ByteOrder.LITTLE, triple^)))


def _int() -> CType:
    return CType.int_type(IntType(IntKind.INT, 4, 4))


def test_shared_children_and_fresh_outputs() raises:
    var shared = ArcPointer(_int())
    var params = List[CParam]()
    params.append(CParam("source_name", shared.copy()))
    var callback = CType.c_function_ptr(CFunctionPtr(shared.copy(), params.copy()))
    var before = dumps_c_type(callback)
    params.append(CParam("unpublished", ArcPointer(_int())))
    var mapper = _mapper()
    var first = mapper.run(callback)
    var second = mapper.run(callback)
    assert_equal(dumps_mojo_type(first), dumps_mojo_type(second))
    assert_equal(dumps_c_type(callback), before)
    match first:
        case .mojo_function_ptr(a):
            match second:
                case .mojo_function_ptr(b):
                    assert_equal(len(a.params), 1)
                    assert_equal(a.params[0].name, "")
                    assert_false(a.ret.ptr() == b.ret.ptr())
                case _:
                    raise Error("expected callback")
        case _:
            raise Error("expected callback")


def test_nominal_recursion_and_context_isolation() raises:
    var node = CType.c_pointer(
        CPointer(
            ArcPointer(
                CType.struct_ref(StructRef("node", "node", "node", size_bytes=16, align_bytes=8))
            )
        )
    )
    validate_type_tree(node)
    _ = _mapper().run(node)
    var char = CType.int_type(IntType(IntKind.CHAR_S, 1, 1))
    var x86 = _mapper(String("x86_64-unknown-linux-gnu"))
    var arm = _mapper(String("aarch64-unknown-linux-gnu"))
    assert_true(dumps_mojo_type(x86.run(char)) != dumps_mojo_type(arm.run(char)))
    assert_equal(dumps_mojo_type(x86.run(char)), dumps_mojo_type(x86.run(char)))


def test_cycle_rejection_and_recovery() raises:
    # Deliberately corrupt the structure, like object.__setattr__ in the Python test.
    var cycle = ArcPointer(CType.c_pointer(CPointer({})))
    cycle[] = CType.c_pointer(CPointer(cycle.copy()))
    var caught = False
    try:
        validate_type_tree(cycle.ptr()[])
    except error:
        caught = String(error) == "structural CIR type cycle"
    # Break the deliberately injected ARC ownership cycle even if validation regresses.
    cycle[] = CType.void_type(VoidType())
    assert_true(caught)
    var mapper = _mapper()
    with assert_raises():
        _ = mapper.run(
            CType.atomic_type(
                AtomicType(
                    ArcPointer(
                        CType.unsupported_type(
                            UnsupportedType(
                                UnsupportedTypeCategory.unknown, "unknown", "unsupported"
                            )
                        )
                    )
                )
            )
        )
    _ = mapper.run(_int())


def test_nested_roundtrip_and_stage_checks() raises:
    var inner = ArcPointer(CType.c_pointer(CPointer(ArcPointer(_int()))))
    var value = CType.c_array(CArray(inner.copy(), 3))
    assert_equal(dumps_c_type(loads_c_type(dumps_c_type(value))), dumps_c_type(value))
    var mapped = _mapper().run(value)
    assert_equal(dumps_mojo_type(loads_mojo_type(dumps_mojo_type(mapped))), dumps_mojo_type(mapped))
    with assert_raises():
        _ = loads_c_type(dumps_mojo_type(mapped))
    with assert_raises():
        _ = loads_mojo_type(dumps_c_type(value))


def test_unicode_and_json_validation() raises:
    assert_equal(mojo_ident("  "), "field")
    assert_equal(mojo_ident("\u2003", "unnamed"), "unnamed")
    assert_equal(normalized_name(" \u2003é三９ "), "é三９")
    assert_equal(normalized_name("²name"), "_²name")
    assert_equal(normalized_name("std"), "std_")
    assert_equal(normalized_name("\U0001F600x"), "_x")
    assert_equal(dump_json(parse_json('"\\ud83d\\ude00"')), '"😀"')
    for invalid in ['{"x":0,"x":1}', '"\\ud800"', "[1,]", "01", "1.5", "true false"]:
        with assert_raises():
            _ = parse_json(invalid)


struct _Tracked(Movable):
    var live: ArcPointer[Int]

    def __init__(out self, var live: ArcPointer[Int]):
        self.live = live^
        self.live[] += 1

    def __deinit__(deinit self):
        self.live[] -= 1


__enum _LifetimeNode(Movable):
    case leaf(_Tracked)
    case owned(OwnedPointer[_LifetimeNode])
    case shared(ArcPointer[_LifetimeNode])

    def __deinit__(deinit self):
        pass


def _count(node: _LifetimeNode) -> Int:
    match node:
        case .leaf(_):
            return 1
        case .owned(child):
            return _count(child.ptr()[])
        case .shared(child):
            return _count(child.ptr()[])


def _unwind(live: ArcPointer[Int]) raises:
    var leaf = _LifetimeNode.leaf(_Tracked(live.copy()))
    var tree = _LifetimeNode.owned(OwnedPointer(leaf^))
    assert_equal(_count(tree), 1)
    raise Error("injected failure")


def test_recursive_destruction_and_exception_unwind() raises:
    var live = ArcPointer(0)
    with assert_raises():
        _unwind(live)
    assert_equal(live.ptr()[], 0)
    var shared = ArcPointer(_LifetimeNode.leaf(_Tracked(live.copy())))
    var other = _LifetimeNode.shared(shared.copy())
    assert_equal(_count(other), 1)
    assert_equal(live.ptr()[], 1)
    other = _LifetimeNode.owned(OwnedPointer(_LifetimeNode.leaf(_Tracked(live.copy()))))
    assert_equal(live.ptr()[], 2)
    assert_equal(_count(other), 1)
    other = _LifetimeNode.shared(shared.copy())
    assert_equal(live.ptr()[], 1)
    assert_equal(_count(other), 1)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
