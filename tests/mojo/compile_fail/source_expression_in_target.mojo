from mojo_bindgen.ir import *
from std.memory import ArcPointer


def main():
    _ = MojoUnaryExpr("-", ArcPointer(CConstExpr.int_literal(IntLiteral(1))))
