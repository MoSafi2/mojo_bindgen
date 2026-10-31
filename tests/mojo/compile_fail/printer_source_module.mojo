from mojo_bindgen.ir import *
from mojo_bindgen.codegen.mojo_ir_printer import render_mojo_module


def main() raises:
    _ = render_mojo_module(Unit("x", "x", "x", TargetABI(8, 8, ByteOrder.LITTLE)))
