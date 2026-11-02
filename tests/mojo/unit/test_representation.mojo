"""Source formats, exact opaque storage, physical fields and call rejection."""
from std.memory import ArcPointer
from std.testing import TestSuite, assert_true, assert_false, assert_equal, assert_raises
from mojo_bindgen.ir import *
from mojo_bindgen.parsing.target_abi import probe_target_abi
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.analysis.facts.representation import target_layout, storage_type
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.mojo.alias_mapping import map_typedef_alias
from mojo_bindgen.analysis.mojo.const_expr_mapping import MapConstExprPass
from mojo_bindgen.analysis.mojo.physical_members import physical_members
from mojo_bindgen.orchestrator import generate_from_unit
from mojo_bindgen.serde import dumps_cir, loads_cir, dumps_mojo_type, loads_mojo_type


def test_float_probe_honors_target_flags() raises:
    var abi = probe_target_abi([])
    var queries = TargetQueries(abi.copy())
    assert_true(queries.float_format(FloatKind.LONG_DOUBLE) == FloatFormat.X87_EXTENDED)
    var mapper = MapTypePass(queries.copy())
    var extended = CType.float_type(FloatType(FloatKind.LONG_DOUBLE, 16, 16))
    assert_true(mapper.run(extended) == MojoType.opaque_storage_type(OpaqueStorageType(16, 16)))
    assert_false(mapper.value_supported(extended))
    abi = probe_target_abi([String("-mlong-double-64")])
    assert_true(
        TargetQueries(abi.copy()).float_format(FloatKind.LONG_DOUBLE) == FloatFormat.BINARY64
    )
    assert_true(
        MapTypePass(TargetQueries(abi.copy())).run(
            CType.float_type(FloatType(FloatKind.LONG_DOUBLE, 8, 8))
        )
        == MojoType.builtin_type(BuiltinType(MojoBuiltin.C_DOUBLE))
    )
    var unit = Unit("float.h", "f", "f", abi.copy())
    assert_true(loads_cir(dumps_cir(unit)) == unit)


def test_storage_geometry_and_expression_guards() raises:
    var queries = TargetQueries(probe_target_abi([]))
    var mapper = MapTypePass(queries.copy())
    var extended = CType.float_type(FloatType(FloatKind.LONG_DOUBLE, 16, 16))
    var expression = MapConstExprPass(mapper.copy())
    assert_true(
        expression.run(CConstExpr.c_size_of_expr(CSizeOfExpr(ArcPointer(extended.copy()))))
        == MojoConstExpr.int_literal(IntLiteral(16))
    )
    with assert_raises():
        _ = expression.run(CConstExpr.c_float_literal(CFloatLiteral("1.0L")))
    var opaque = storage_type(32, 16)
    assert_true(loads_mojo_type(dumps_mojo_type(opaque)) == opaque)
    assert_true(target_layout(opaque, queries).value() == (32, 16))
    assert_true(storage_type(8, 16) == MojoType.builtin_type(BuiltinType(MojoBuiltin.UNSUPPORTED)))


def test_padding_is_one_member_per_physical_field() raises:
    var decl = StructDecl("Padded")
    decl.members.append(StructMember.padding_member(PaddingMember("pad", 12, 4)))
    var members = physical_members(decl)
    assert_equal(len(members), 2)
    if case .padding_member(first) = members[0]:
        assert_equal(first.name, "pad_0")
        assert_equal(first.storage_width_bytes, 4)
    if case .padding_member(last) = members[1]:
        assert_equal(last.name, "pad_1")
        assert_equal(last.byte_offset, 8)
        assert_equal(last.storage_width_bytes, 8)


def test_integer_alias_names_cannot_override_source_semantics() raises:
    var mapper = MapTypePass(TargetQueries(probe_target_abi([])))
    var alias = map_typedef_alias("uint32_t", CType.int_type(IntType(IntKind.INT, 4, 4)), mapper)
    assert_true(alias)
    assert_true(
        alias.value().type_value.value()[] == MojoType.builtin_type(BuiltinType(MojoBuiltin.C_INT))
    )


def test_extended_record_layout_and_call_safety() raises:
    var unit = Unit("a.h", "a", "a", probe_target_abi([]))
    var fields = List[Field]()
    fields.append(
        Field(
            "first",
            "first",
            ArcPointer(CType.int_type(IntType(IntKind.LONGLONG, 8, 8))),
            0,
            size_bytes=8,
        )
    )
    fields.append(
        Field(
            "extended",
            "extended",
            ArcPointer(CType.float_type(FloatType(FloatKind.LONG_DOUBLE, 16, 16))),
            16,
            size_bytes=16,
        )
    )
    unit.decls.append(Decl.struct_decl(Struct("aligned", "Aligned", "Aligned", fields^, 32, 16)))
    unit.decls.append(
        Decl.function(
            Function(
                "echo",
                "echo",
                ArcPointer(CType.float_type(FloatType(FloatKind.LONG_DOUBLE, 16, 16))),
                List[CParam](),
            )
        )
    )
    var result = generate_from_unit(unit)
    assert_true("var storage: Array[UInt8, 32]" in result.bindings_source)
    assert_true("@align(16)" in result.bindings_source)
    assert_true("callable binding omitted" in result.bindings_source)
    assert_false('return external_call["echo"' in result.bindings_source)


def test_unknown_storage_stubs_do_not_abort_other_declarations() raises:
    var unit = Unit("a.h", "a", "a", probe_target_abi([]))
    var unknown = ArcPointer(CType.float_type(FloatType(FloatKind.DOUBLE, 8, 16)))
    unit.decls.append(Decl.function(Function("bad", "bad", unknown.copy(), List[CParam]())))
    unit.decls.append(Decl.global_var(GlobalVar("g", "bad_global", "bad_global", unknown.copy())))
    unit.decls.append(
        Decl.function(
            Function("good", "good", ArcPointer(CType.void_type(VoidType())), List[CParam]())
        )
    )
    var result = generate_from_unit(unit)
    assert_true("# <unsupported> bad(" in result.bindings_source)
    assert_true("# global variable bad_global: <unsupported>" in result.bindings_source)
    assert_true("def good(" in result.bindings_source)


def main() raises:
    TestSuite.discover_tests[__functions_in_module()]().run()
