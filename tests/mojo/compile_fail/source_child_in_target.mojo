from std.memory import ArcPointer
from mojo_bindgen.ir import *


def main():
    var source = ArcPointer(CType.int_type(IntType(IntKind.INT, 4)))
    _ = MojoArray(source^, 3)
