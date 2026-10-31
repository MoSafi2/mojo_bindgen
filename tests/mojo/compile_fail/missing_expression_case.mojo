from mojo_bindgen.ir import *


def broken(expr: MojoConstExpr) -> Int:
    match expr:
        case .int_literal(_):
            return 1
        case .mojo_float_literal(_):
            return 2
        case .string_literal(_):
            return 3
        case .char_literal(_):
            return 4
        case .mojo_ref_expr(_):
            return 5
        case .mojo_unary_expr(_):
            return 6
        case .mojo_binary_expr(_):
            return 7
        case .mojo_cast_expr(_):
            return 8
        case .mojo_call_expr(_):
            return 9


def main():
    _ = broken(MojoConstExpr.int_literal(IntLiteral(1)))
