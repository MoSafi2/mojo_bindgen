from std.memory import ArcPointer
from ...ir import *
from .type_mapping import MapTypePass


def _integral(t: MojoType) -> Bool:
    match t:
        case .builtin_type(v):
            match v.name:
                case .INT8 | .C_CHAR | .C_UCHAR | .C_SHORT | .C_USHORT | .C_INT | .C_UINT | .C_LONG | .C_ULONG | .C_LONG_LONG | .C_ULONG_LONG | .INT128 | .UINT128:
                    return True
                case _:
                    return False
        case _:
            return False


def _coerce(value: MojoConstExpr, t: MojoType) -> MojoConstExpr:
    match value:
        case .int_literal(_):
            return MojoConstExpr.mojo_cast_expr(
                MojoCastExpr(ArcPointer(t.copy()), ArcPointer(value.copy()))
            )
        case .mojo_unary_expr(v):
            return MojoConstExpr.mojo_unary_expr(
                MojoUnaryExpr(v.op.copy(), ArcPointer(_coerce(v.operand.ptr()[], t)))
            )
        case .mojo_binary_expr(v):
            return MojoConstExpr.mojo_binary_expr(
                MojoBinaryExpr(
                    v.op.copy(),
                    ArcPointer(_coerce(v.lhs.ptr()[], t)),
                    ArcPointer(_coerce(v.rhs.ptr()[], t)),
                )
            )
        case _:
            return value.copy()


def typed_const_value(
    value: MojoConstExpr, decl_type: CType, type_mapper: MapTypePass
) raises -> MojoConstExpr:
    if not type_mapper.value_supported(decl_type):
        raise Error("constant type has no supported Mojo value representation")
    var mapped = type_mapper.run(decl_type)
    return _coerce(value, mapped) if _integral(mapped) else value.copy()
