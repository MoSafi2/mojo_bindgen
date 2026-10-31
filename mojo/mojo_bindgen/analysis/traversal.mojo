"""Typed source declaration, expression and type traversal."""
from std.memory import ArcPointer
from ..ir import *
from .type_walk import TypeWalkOptions, iter_type_nodes


def decl_id(decl: Decl) -> Optional[String]:
    match decl:
        case .function(v):
            return v.decl_id.copy() if v.decl_id.byte_length() else Optional[String]()
        case .struct_decl(v):
            return v.decl_id.copy() if v.decl_id.byte_length() else Optional[String]()
        case .enum_decl(v):
            return v.decl_id.copy() if v.decl_id.byte_length() else Optional[String]()
        case .typedef(v):
            return v.decl_id.copy() if v.decl_id.byte_length() else Optional[String]()
        case .global_var(v):
            return v.decl_id.copy() if v.decl_id.byte_length() else Optional[String]()
        case .const_decl(_) | .macro_decl(_):
            return {}


def decl_name(decl: Decl) -> String:
    match decl:
        case .function(v):
            return v.name.copy()
        case .struct_decl(v):
            return v.name.copy()
        case .enum_decl(v):
            return v.name.copy()
        case .typedef(v):
            return v.name.copy()
        case .global_var(v):
            return v.name.copy()
        case .const_decl(v):
            return v.name.copy()
        case .macro_decl(v):
            return v.name.copy()


def iter_decl_types(decl: Decl) -> List[ArcPointer[CType]]:
    var out = List[ArcPointer[CType]]()
    match decl:
        case .function(v):
            out.append(v.ret.copy())
            for p in v.params:
                out.append(p.type.copy())
        case .struct_decl(v):
            for f in v.fields:
                out.append(f.type.copy())
        case .enum_decl(v):
            out.append(ArcPointer(CType.int_type(v.underlying.copy())))
        case .typedef(v):
            out.append(v.aliased.copy())
            out.append(v.canonical.copy())
        case .global_var(v):
            out.append(v.type.copy())
        case .const_decl(v):
            out.append(v.type.copy())
        case .macro_decl(v):
            if v.type:
                out.append(v.type.value().copy())
    return out^


def iter_decl_const_exprs(decl: Decl) -> List[ArcPointer[CConstExpr]]:
    var out = List[ArcPointer[CConstExpr]]()
    match decl:
        case .global_var(v):
            if v.initializer:
                out.append(v.initializer.value().copy())
        case .const_decl(v):
            out.append(v.expr.copy())
        case .macro_decl(v):
            if v.expr:
                out.append(v.expr.value().copy())
        case .function(_) | .struct_decl(_) | .enum_decl(_) | .typedef(_):
            pass
    return out^


def expression_children(expr: CConstExpr) -> List[ArcPointer[CConstExpr]]:
    var out = List[ArcPointer[CConstExpr]]()
    match expr:
        case .c_unary_expr(v):
            out.append(v.operand.copy())
        case .c_binary_expr(v):
            out.append(v.lhs.copy())
            out.append(v.rhs.copy())
        case .c_cast_expr(v):
            out.append(v.expr.copy())
        case .c_call_expr(v):
            out.append(v.callee.copy())
            out.extend(v.args.copy())
        case .int_literal(_) | .c_float_literal(_) | .string_literal(_) | .char_literal(
            _
        ) | .c_null_ptr_literal(_) | .c_ref_expr(_) | .c_size_of_expr(_):
            pass
    return out^


def _validate_expr(expr: ArcPointer[CConstExpr], mut active: List[ArcPointer[CConstExpr]]) raises:
    for p in active:
        if expr.ptr() == p.ptr():
            raise Error("structural CIR expression cycle")
    active.append(expr.copy())
    for child in expression_children(expr.ptr()[]):
        _validate_expr(child, active)
    _ = active.pop()


def validate_expression(expr: CConstExpr) raises:
    var active = List[ArcPointer[CConstExpr]]()
    for child in expression_children(expr):
        _validate_expr(child, active)


def iter_const_expr_types(expr: CConstExpr) -> List[ArcPointer[CType]]:
    var out = List[ArcPointer[CType]]()
    match expr:
        case .c_cast_expr(v):
            out.append(v.target.copy())
        case .c_size_of_expr(v):
            out.append(v.target.copy())
        case _:
            pass
    for child in expression_children(expr):
        out.extend(iter_const_expr_types(child.ptr()[]))
    return out^


def iter_const_expr_refs(expr: CConstExpr) -> List[String]:
    var out = List[String]()
    match expr:
        case .c_ref_expr(v):
            out.append(v.name.copy())
        case _:
            pass
    for child in expression_children(expr):
        out.extend(iter_const_expr_refs(child.ptr()[]))
    return out^


def iter_decl_referenced_types(decl: Decl) -> List[ArcPointer[CType]]:
    var result = iter_decl_types(decl)
    for expr in iter_decl_const_exprs(decl):
        result.extend(iter_const_expr_types(expr.ptr()[]))
    return result^


def referenced_id(t: CType) -> Optional[String]:
    match t:
        case .type_ref(v):
            return v.decl_id.copy()
        case .struct_ref(v):
            return v.decl_id.copy()
        case .enum_ref(v):
            return v.decl_id.copy()
        case .opaque_record_ref(v):
            return v.decl_id.copy()
        case _:
            return {}


def expression_children(expr: MojoConstExpr) -> List[ArcPointer[MojoConstExpr]]:
    var out = List[ArcPointer[MojoConstExpr]]()
    match expr:
        case .mojo_unary_expr(v):
            out.append(v.operand.copy())
        case .mojo_binary_expr(v):
            out.append(v.lhs.copy())
            out.append(v.rhs.copy())
        case .mojo_cast_expr(v):
            out.append(v.expr.copy())
        case .mojo_call_expr(v):
            out.append(v.callee.copy())
            out.extend(v.args.copy())
        case .int_literal(_) | .mojo_float_literal(_) | .string_literal(_) | .char_literal(
            _
        ) | .mojo_ref_expr(_) | .mojo_size_of_expr(_):
            pass
    return out^


def _validate_expr(
    expr: ArcPointer[MojoConstExpr], mut active: List[ArcPointer[MojoConstExpr]]
) raises:
    for prior in active:
        if expr.ptr() == prior.ptr():
            raise Error("structural MojoIR expression cycle")
    active.append(expr.copy())
    for child in expression_children(expr.ptr()[]):
        _validate_expr(child, active)
    _ = active.pop()


def validate_expression(expr: MojoConstExpr) raises:
    var active = List[ArcPointer[MojoConstExpr]]()
    for child in expression_children(expr):
        _validate_expr(child, active)


def _validate_target_expr_types(expr: MojoConstExpr) raises:
    from .type_walk import validate_type_tree

    match expr:
        case .mojo_cast_expr(v):
            validate_type_tree(v.target.ptr()[])
        case .mojo_size_of_expr(v):
            validate_type_tree(v.target.ptr()[])
        case _:
            pass
    for child in expression_children(expr):
        _validate_target_expr_types(child.ptr()[])


def validate_mojo_module(module: MojoModule) raises:
    from .type_walk import validate_type_tree

    for decl in module.decls:
        var types = List[ArcPointer[MojoType]]()
        var exprs = List[ArcPointer[MojoConstExpr]]()
        match decl:
            case .alias_decl(v):
                if v.type_value:
                    types.append(v.type_value.value().copy())
                if v.const_type:
                    types.append(v.const_type.value().copy())
                if v.const_value:
                    exprs.append(v.const_value.value().copy())
            case .global_decl(v):
                types.append(v.value_type.copy())
            case .function_decl(v):
                types.append(v.return_type.copy())
                for p in v.params:
                    types.append(p.type.copy())
            case .struct_decl(v):
                for m in v.members:
                    match m:
                        case .stored_member(s):
                            types.append(s.type.copy())
                        case .bitfield_group_member(s):
                            types.append(s.storage_type.copy())
                            for f in s.fields:
                                types.append(f.logical_type.copy())
                        case .padding_member(_) | .opaque_storage_member(_):
                            pass
                for m in v.comptime_members:
                    if m.type_value:
                        types.append(m.type_value.value().copy())
                    if m.const_value:
                        exprs.append(m.const_value.value().copy())
                for init in v.initializers:
                    for p in init.params:
                        types.append(p.type.copy())
                if v.flexible_tail:
                    types.append(v.flexible_tail.value().element_type.copy())
        for t in types:
            validate_type_tree(t.ptr()[])
        for e in exprs:
            validate_expression(e.ptr()[])
            _validate_target_expr_types(e.ptr()[])
