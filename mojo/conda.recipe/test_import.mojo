from mojo_bindgen.ir import IntKind, IntType, CType, TargetABI, ByteOrder
from mojo_bindgen.type_mapping import MapTypePass, TargetQueries
from mojo_bindgen.serde import dumps_mojo_type
from std.testing import assert_equal


def main() raises:
    var mapper = MapTypePass(TargetQueries(TargetABI(8, 8, ByteOrder.LITTLE)))
    var value = CType.int_type(IntType(IntKind.INT, 4, 4))
    assert_equal(
        dumps_mojo_type(mapper.run(value)), '{"kind":"BuiltinType","fields":{"name":"c_int"}}'
    )
