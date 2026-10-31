from mojo_bindgen.ir import *
from mojo_bindgen.type_mapping import MapTypePass, TargetQueries


def main() raises:
    var mapper = MapTypePass(TargetQueries(TargetABI(8, 8, ByteOrder.LITTLE)))
    _ = mapper.run(MojoType.builtin_type(BuiltinType(MojoBuiltin.C_INT)))
