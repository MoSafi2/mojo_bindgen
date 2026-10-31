from std.memory import ArcPointer
from ...ir import *


@fieldwise_init
struct EnumResolution(Copyable, Movable):
    var name: String
    var aliases: List[String]


def rewrite_type(value: CType, names: Dict[String, EnumResolution]) raises -> CType:
    match value:
        case .void_type(original):
            var v = original.copy()
            return CType.void_type(v^)
        case .int_type(original):
            var v = original.copy()
            return CType.int_type(v^)
        case .float_type(original):
            var v = original.copy()
            return CType.float_type(v^)
        case .qualified_type(original):
            var v = original.copy()
            v.unqualified = ArcPointer(rewrite_type(v.unqualified.ptr()[], names))
            return CType.qualified_type(v^)
        case .atomic_type(original):
            var v = original.copy()
            v.value_type = ArcPointer(rewrite_type(v.value_type.ptr()[], names))
            return CType.atomic_type(v^)
        case .c_pointer(original):
            var v = original.copy()
            if v.pointee:
                v.pointee = ArcPointer(rewrite_type(v.pointee.value().ptr()[], names))
            return CType.c_pointer(v^)
        case .c_array(original):
            var v = original.copy()
            v.element = ArcPointer(rewrite_type(v.element.ptr()[], names))
            return CType.c_array(v^)
        case .c_function_ptr(original):
            var v = original.copy()
            v.ret = ArcPointer(rewrite_type(v.ret.ptr()[], names))
            for i in range(len(v.params)):
                v.params[i].type = ArcPointer(rewrite_type(v.params[i].type.ptr()[], names))
            return CType.c_function_ptr(v^)
        case .opaque_record_ref(original):
            var v = original.copy()
            return CType.opaque_record_ref(v^)
        case .unsupported_type(original):
            var v = original.copy()
            return CType.unsupported_type(v^)
        case .complex_type(original):
            var v = original.copy()
            return CType.complex_type(v^)
        case .vector_type(original):
            var v = original.copy()
            v.element = ArcPointer(rewrite_type(v.element.ptr()[], names))
            return CType.vector_type(v^)
        case .struct_ref(original):
            var v = original.copy()
            return CType.struct_ref(v^)
        case .enum_ref(original):
            var v = original.copy()
            if v.decl_id in names:
                v.name = names[v.decl_id].name.copy()
            return CType.enum_ref(v^)
        case .type_ref(original):
            var v = original.copy()
            v.canonical = ArcPointer(rewrite_type(v.canonical.ptr()[], names))
            return CType.type_ref(v^)


def rewrite_expr(value: CConstExpr, names: Dict[String, EnumResolution]) raises -> CConstExpr:
    match value:
        case .int_literal(original):
            var v = original.copy()
            return CConstExpr.int_literal(v^)
        case .c_float_literal(original):
            var v = original.copy()
            return CConstExpr.c_float_literal(v^)
        case .string_literal(original):
            var v = original.copy()
            return CConstExpr.string_literal(v^)
        case .char_literal(original):
            var v = original.copy()
            return CConstExpr.char_literal(v^)
        case .c_null_ptr_literal(original):
            var v = original.copy()
            return CConstExpr.c_null_ptr_literal(v^)
        case .c_ref_expr(original):
            var v = original.copy()
            return CConstExpr.c_ref_expr(v^)
        case .c_unary_expr(original):
            var v = original.copy()
            v.operand = ArcPointer(rewrite_expr(v.operand.ptr()[], names))
            return CConstExpr.c_unary_expr(v^)
        case .c_binary_expr(original):
            var v = original.copy()
            v.lhs = ArcPointer(rewrite_expr(v.lhs.ptr()[], names))
            v.rhs = ArcPointer(rewrite_expr(v.rhs.ptr()[], names))
            return CConstExpr.c_binary_expr(v^)
        case .c_cast_expr(original):
            var v = original.copy()
            v.target = ArcPointer(rewrite_type(v.target.ptr()[], names))
            v.expr = ArcPointer(rewrite_expr(v.expr.ptr()[], names))
            return CConstExpr.c_cast_expr(v^)
        case .c_size_of_expr(original):
            var v = original.copy()
            v.target = ArcPointer(rewrite_type(v.target.ptr()[], names))
            return CConstExpr.c_size_of_expr(v^)
        case .c_call_expr(original):
            var v = original.copy()
            v.callee = ArcPointer(rewrite_expr(v.callee.ptr()[], names))
            for i in range(len(v.args)):
                v.args[i] = ArcPointer(rewrite_expr(v.args[i].ptr()[], names))
            return CConstExpr.c_call_expr(v^)


def rewrite_decl(value: Decl, names: Dict[String, EnumResolution]) raises -> Decl:
    match value:
        case .function(original):
            var v = original.copy()
            v.ret = ArcPointer(rewrite_type(v.ret.ptr()[], names))
            for i in range(len(v.params)):
                v.params[i].type = ArcPointer(rewrite_type(v.params[i].type.ptr()[], names))
            return Decl.function(v^)
        case .struct_decl(original):
            var v = original.copy()
            for i in range(len(v.fields)):
                v.fields[i].type = ArcPointer(rewrite_type(v.fields[i].type.ptr()[], names))
            return Decl.struct_decl(v^)
        case .enum_decl(original):
            var v = original.copy()
            if v.decl_id in names:
                v.name = names[v.decl_id].name.copy()
                v.alias_names = names[v.decl_id].aliases.copy()
                for i in range(len(v.enumerants)):
                    v.enumerants[i].enum_decl_id = v.decl_id.copy()
            return Decl.enum_decl(v^)
        case .typedef(original):
            var v = original.copy()
            v.aliased = ArcPointer(rewrite_type(v.aliased.ptr()[], names))
            v.canonical = ArcPointer(rewrite_type(v.canonical.ptr()[], names))
            return Decl.typedef(v^)
        case .const_decl(original):
            var v = original.copy()
            v.type = ArcPointer(rewrite_type(v.type.ptr()[], names))
            v.expr = ArcPointer(rewrite_expr(v.expr.ptr()[], names))
            return Decl.const_decl(v^)
        case .macro_decl(original):
            var v = original.copy()
            if v.expr:
                v.expr = ArcPointer(rewrite_expr(v.expr.value().ptr()[], names))
            if v.type:
                v.type = ArcPointer(rewrite_type(v.type.value().ptr()[], names))
            return Decl.macro_decl(v^)
        case .global_var(original):
            var v = original.copy()
            v.type = ArcPointer(rewrite_type(v.type.ptr()[], names))
            return Decl.global_var(v^)
