from std.memory import ArcPointer
from ...ir import *
from ..._numbers import parse_float, parse_hex_float
from ..traversal import validate_expression
from ..common import mojo_ident, mojo_float_literal_text
from .type_mapping import MapTypePass


@fieldwise_init
struct MapConstExprPass(Copyable, Movable):
    var type_mapping: MapTypePass

    def run(self, expr: CConstExpr) raises -> MojoConstExpr:
        validate_expression(expr)
        return self._run(expr)

    def _run(self, expr: CConstExpr) raises -> MojoConstExpr:
        match expr:
            case .int_literal(v):
                return MojoConstExpr.int_literal(v.copy())
            case .string_literal(v):
                return MojoConstExpr.string_literal(v.copy())
            case .char_literal(v):
                return MojoConstExpr.char_literal(v.copy())
            case .c_float_literal(v):
                var text = mojo_float_literal_text(v.spelling)
                var lowered = text.lower()
                var value: Float64
                if (
                    lowered.startswith("0x")
                    or lowered.startswith("+0x")
                    or lowered.startswith("-0x")
                ):
                    value = parse_hex_float(text)
                else:
                    value = parse_float(text)
                return MojoConstExpr.mojo_float_literal(MojoFloatLiteral(value))
            case .c_ref_expr(v):
                return MojoConstExpr.mojo_ref_expr(MojoRefExpr(mojo_ident(v.name)))
            case .c_unary_expr(v):
                return MojoConstExpr.mojo_unary_expr(
                    MojoUnaryExpr(v.op.copy(), ArcPointer(self._run(v.operand.ptr()[])))
                )
            case .c_binary_expr(v):
                return MojoConstExpr.mojo_binary_expr(
                    MojoBinaryExpr(
                        v.op.copy(),
                        ArcPointer(self._run(v.lhs.ptr()[])),
                        ArcPointer(self._run(v.rhs.ptr()[])),
                    )
                )
            case .c_cast_expr(v):
                return MojoConstExpr.mojo_cast_expr(
                    MojoCastExpr(
                        ArcPointer(self.type_mapping.run(v.target.ptr()[])),
                        ArcPointer(self._run(v.expr.ptr()[])),
                    )
                )
            case .c_size_of_expr(v):
                return MojoConstExpr.mojo_size_of_expr(
                    MojoSizeOfExpr(ArcPointer(self.type_mapping.run(v.target.ptr()[])))
                )
            case .c_call_expr(v):
                var args = List[ArcPointer[MojoConstExpr]]()
                for a in v.args:
                    args.append(ArcPointer(self._run(a.ptr()[])))
                return MojoConstExpr.mojo_call_expr(
                    MojoCallExpr(ArcPointer(self._run(v.callee.ptr()[])), args^)
                )
            case .c_null_ptr_literal(_):
                raise Error("nullptr constants do not have a valid MojoIR literal form")
