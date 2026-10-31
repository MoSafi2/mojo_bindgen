from mojo_bindgen.ir import IntKind, IntType, CType, TargetABI, ByteOrder
from mojo_bindgen.analysis.mojo.type_mapping import MapTypePass
from mojo_bindgen.analysis.facts.target import TargetQueries
from mojo_bindgen.serde import dumps_mojo_type
from std.testing import assert_equal


def main() raises:
    test_installed_backend()
    var mapper = MapTypePass(TargetQueries(TargetABI(8, 8, ByteOrder.LITTLE)))
    var value = CType.int_type(IntType(IntKind.INT, 4, 4))
    assert_equal(
        dumps_mojo_type(mapper.run(value)), '{"kind":"BuiltinType","fields":{"name":"c_int"}}'
    )


def test_installed_backend() raises:
    from mojo_bindgen import generate_from_unit
    from mojo_bindgen.ir import Unit, Decl, Const, CConstExpr, IntLiteral, IntegerValue
    from std.memory import ArcPointer
    from std.testing import assert_true

    var unit = Unit("installed.h", "installed", "installed", TargetABI(8, 8, ByteOrder.LITTLE))
    var integer = IntegerValue.from_decimal(
        "123456789012345678901234567890123456789012345678901234567890"
    )
    unit.decls.append(
        Decl.const_decl(
            Const(
                "N",
                ArcPointer(CType.int_type(IntType(IntKind.INT, 4, 4))),
                ArcPointer(CConstExpr.int_literal(IntLiteral(integer^))),
            )
        )
    )
    var result = generate_from_unit(unit, layout_module_name=String("bindings"))
    assert_true(
        "123456789012345678901234567890123456789012345678901234567890" in result.bindings_source
    )
    assert_true("def main() raises:" in result.layout_test_source.value())
