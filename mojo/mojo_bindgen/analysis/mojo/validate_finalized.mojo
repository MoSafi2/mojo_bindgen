"""Check contracts required by the source printer after target normalization."""
from ...ir import *
from ..traversal import validate_mojo_module
from .record_policies import _PolicyState, _trivial_name


def _type(t: MojoType, callback: Bool = False) raises:
    match t:
        case .opaque_storage_type(_):
            raise Error("unresolved opaque storage in finalized MojoIR")
        case .builtin_type(_) | .named_type(_):
            pass
        case .mojo_pointer(v):
            if v.pointee:
                _type(v.pointee.value()[])
        case .mojo_array(v):
            _type(v.element[])
        case .parametric_type(v):
            for arg in v.args:
                if case .type_arg(a) = arg:
                    _type(a.type[])
        case .mojo_function_ptr(v):
            if not callback:
                raise Error("unresolved callback signature in finalized MojoIR")
            if v.abi != "C" or not v.thin or v.raises_error:
                raise Error("callback signature must be thin, non-raising and use the C ABI")
            _type(v.ret[])
            for param in v.params:
                _type(param.type[])


def _expr(expr: MojoConstExpr) raises:
    match expr:
        case .mojo_unary_expr(v):
            _expr(v.operand[])
        case .mojo_binary_expr(v):
            _expr(v.lhs[])
            _expr(v.rhs[])
        case .mojo_cast_expr(v):
            _type(v.target[])
            _expr(v.expr[])
        case .mojo_size_of_expr(v):
            _type(v.target[])
        case .mojo_call_expr(v):
            _expr(v.callee[])
            for arg in v.args:
                _expr(arg[])
        case .int_literal(_) | .mojo_float_literal(_) | .string_literal(_) | .char_literal(
            _
        ) | .mojo_ref_expr(_):
            pass


def _extern_type(t: MojoType, state: _PolicyState, mut active: Dict[String, Bool]) raises -> Bool:
    match t:
        case .opaque_storage_type(_):
            return False
        case .builtin_type(v):
            return v.name != MojoBuiltin.UNSUPPORTED
        case .mojo_pointer(_) | .mojo_function_ptr(_):
            return True
        case .mojo_array(v):
            return v.size > 0 and _extern_type(v.element[], state, active)
        case .parametric_type(_):
            return False
        case .named_type(v):
            if _trivial_name(v.name):
                return True
            if v.name in active:
                return False
            active[v.name] = True
            var result = False
            if v.name in state.aliases:
                ref alias = state.aliases[v.name]
                if alias.kind == AliasKind.CALLBACK_SIGNATURE:
                    result = True
                elif alias.kind == AliasKind.TYPE_ALIAS and alias.type_value:
                    result = _extern_type(alias.type_value.value()[], state, active)
            elif v.name in state.structs:
                ref record = state.structs[v.name]
                result = (
                    record.kind == StructKind.PLAIN
                    and not record.flexible_tail
                    and len(record.members) > 0
                )
                for member in record.members:
                    match member:
                        case .stored_member(field):
                            result = result and _extern_type(field.type[], state, active)
                        case .padding_member(_) | .opaque_storage_member(
                            _
                        ) | .bitfield_group_member(_):
                            result = False
            _ = active.pop(v.name)
            return result


def _dependencies(actual: ModuleDependencies, required: ModuleDependencies) raises:
    var imports = Dict[String, Bool]()
    for item in actual.imports:
        for name in item.names:
            imports[item.module + ":" + name] = True
    for item in required.imports:
        for name in item.names:
            if item.module + ":" + name not in imports:
                raise Error("missing finalized import: " + item.module + "." + name)
    var supports = Dict[String, Bool]()
    for item in actual.support_decls:
        supports[item.kind.value()] = True
    for item in required.support_decls:
        if item.kind.value() not in supports:
            raise Error("missing finalized support declaration: " + item.kind.value())


def validate_finalized_mojo_module(module: MojoModule, required: ModuleDependencies) raises:
    validate_mojo_module(module)
    _dependencies(module.dependencies, required)
    var state = _PolicyState(module)
    var names = Dict[String, Bool]()
    for decl in module.decls:
        var name: String
        var emits_name = True
        match decl:
            case .alias_decl(v):
                name = v.name.copy()
                emits_name = Bool(v.type_value) or Bool(v.const_value)
                if v.kind == AliasKind.CALLBACK_SIGNATURE and not v.type_value:
                    raise Error("callback alias has no signature: " + v.name)
                if v.type_value:
                    if v.kind == AliasKind.CALLBACK_SIGNATURE:
                        match v.type_value.value()[]:
                            case .mojo_function_ptr(_):
                                pass
                            case _:
                                raise Error("callback alias has no function type: " + v.name)
                    _type(v.type_value.value()[], v.kind == AliasKind.CALLBACK_SIGNATURE)
                if v.const_type:
                    _type(v.const_type.value()[])
                if v.const_value:
                    _expr(v.const_value.value()[])
            case .global_decl(v):
                name = v.name.copy()
                emits_name = v.kind == GlobalKind.WRAPPER
                _type(v.value_type[])
            case .struct_decl(v):
                name = v.name.copy()
                for member in v.members:
                    match member:
                        case .stored_member(field):
                            _type(field.type[])
                        case .bitfield_group_member(group):
                            _type(group.storage_type[])
                            for field in group.fields:
                                _type(field.logical_type[])
                        case .padding_member(p):
                            if p.storage_width_bytes != p.size_bytes or (
                                p.storage_width_bytes != 1
                                and p.storage_width_bytes != 2
                                and p.storage_width_bytes != 4
                                and p.storage_width_bytes != 8
                            ):
                                raise Error("unresolved padding in finalized MojoIR")
                        case .opaque_storage_member(p):
                            if p.size_bytes < 0:
                                raise Error("negative opaque storage size")
                for member in v.comptime_members:
                    if member.type_value:
                        _type(member.type_value.value()[])
                    if member.const_value:
                        _expr(member.const_value.value()[])
                for initializer in v.initializers:
                    for param in initializer.params:
                        _type(param.type[])
                if v.flexible_tail:
                    _type(v.flexible_tail.value().element_type[])
            case .function_decl(v):
                name = v.name.copy()
                emits_name = (
                    v.kind == FunctionKind.WRAPPER or v.kind == FunctionKind.EXTERN_DECLARATION
                )
                _type(v.return_type[])
                for param in v.params:
                    _type(param.type[])
                if v.kind == FunctionKind.WRAPPER and (
                    state.type_passability(v.return_type[]) == MojoPassability.MEMORY_ONLY
                ):
                    raise Error("wrapper return is not RegisterPassable: " + v.name)
                if v.kind == FunctionKind.WRAPPER or v.kind == FunctionKind.EXTERN_DECLARATION:
                    if not v.call_target.symbol and not v.link_name:
                        raise Error("call target has no symbol: " + v.name)
                    if v.attrs.inline_disposition != InlineDisposition.NONE:
                        raise Error("inline source directive was not lowered: " + v.name)
                if v.kind == FunctionKind.EXTERN_DECLARATION:
                    if v.call_target.link_mode != LinkMode.EXTERNAL_CALL or v.num_fixed_args:
                        raise Error(
                            "external declaration requires fixed direct C linking: " + v.name
                        )
                    var active = Dict[String, Bool]()
                    if not _extern_type(v.return_type[], state, active):
                        raise Error("external declaration has an ineligible return: " + v.name)
                    for param in v.params:
                        if not _extern_type(param.type[], state, active):
                            raise Error(
                                "external declaration has an ineligible argument: " + v.name
                            )
                elif v.kind == FunctionKind.WRAPPER and v.num_fixed_args:
                    if (
                        v.call_target.link_mode != LinkMode.EXTERNAL_CALL
                        or v.num_fixed_args.value() != len(v.params)
                    ):
                        raise Error("invalid finalized variadic call: " + v.name)
        if emits_name:
            if name in names:
                raise Error("duplicate finalized declaration: " + name)
            names[name] = True
