from ...ir import *
from ..traversal import validate_mojo_module


@fieldwise_init
struct TransferTraits(Copyable, Movable):
    var copyable: Bool
    var movable: Bool


def has_opaque_storage(decl: StructDecl) -> Bool:
    for m in decl.members:
        match m:
            case .opaque_storage_member(_):
                return True
            case _:
                pass
    return False


def has_atomic_storage(decl: StructDecl) -> Bool:
    for m in decl.members:
        match m:
            case .stored_member(v):
                match v.type.ptr()[]:
                    case .parametric_type(p):
                        if p.base == ParametricBase.ATOMIC:
                            return True
                    case _:
                        pass
            case _:
                pass
    return False


def is_pure_bitfield(decl: StructDecl) -> Bool:
    if not len(decl.members):
        return False
    for m in decl.members:
        match m:
            case .bitfield_group_member(_):
                pass
            case _:
                return False
    return True


def _trivial_name(name: String) -> Bool:
    for token in String(
        "Bool|Byte|Float16|Float32|Float64|Int|Int8|Int16|Int32|Int64|Int128|UInt|UInt8|UInt16|UInt32|UInt64|UInt128"
    ).split("|"):
        if name == token:
            return True
    return False


struct _PolicyState(Movable):
    var structs: Dict[String, StructDecl]
    var aliases: Dict[String, AliasDecl]
    var passabilities: Dict[String, MojoPassability]
    var computing_pass: Dict[String, Bool]
    var transfers: Dict[String, TransferTraits]
    var computing_transfer: Dict[String, Bool]

    def __init__(out self, module: MojoModule):
        self.structs = Dict[String, StructDecl]()
        self.aliases = Dict[String, AliasDecl]()
        self.passabilities = Dict[String, MojoPassability]()
        self.computing_pass = Dict[String, Bool]()
        self.transfers = Dict[String, TransferTraits]()
        self.computing_transfer = Dict[String, Bool]()
        for d in module.decls:
            match d:
                case .struct_decl(v):
                    self.structs[v.name] = v.copy()
                case .alias_decl(v):
                    self.aliases[v.name] = v.copy()
                case _:
                    pass

    def type_passability(mut self, t: MojoType) raises -> MojoPassability:
        match t:
            case .builtin_type(v):
                return (
                    MojoPassability.MEMORY_ONLY if v.name
                    == MojoBuiltin.UNSUPPORTED else MojoPassability.TRIVIAL_REGISTER_PASSABLE
                )
            case .mojo_function_ptr(_):
                return MojoPassability.TRIVIAL_REGISTER_PASSABLE
            case .mojo_pointer(v):
                return (
                    MojoPassability.REGISTER_PASSABLE if v.nullable else MojoPassability.TRIVIAL_REGISTER_PASSABLE
                )
            case .mojo_array(_):
                return MojoPassability.MEMORY_ONLY
            case .parametric_type(v):
                return (
                    MojoPassability.TRIVIAL_REGISTER_PASSABLE if v.base == ParametricBase.SIMD
                    or v.base == ParametricBase.COMPLEX_SIMD else MojoPassability.MEMORY_ONLY
                )
            case .named_type(v):
                if _trivial_name(v.name):
                    return MojoPassability.TRIVIAL_REGISTER_PASSABLE
                if v.name in self.structs:
                    return self.record_passability(v.name)
                if v.name not in self.aliases:
                    return MojoPassability.MEMORY_ONLY
                var alias = self.aliases[v.name].copy()
                if alias.kind == AliasKind.CALLBACK_SIGNATURE:
                    return MojoPassability.TRIVIAL_REGISTER_PASSABLE
                if alias.kind != AliasKind.TYPE_ALIAS or not alias.type_value:
                    return MojoPassability.MEMORY_ONLY
                return self.type_passability(alias.type_value.value().ptr()[])

    def record_passability(mut self, name: String) raises -> MojoPassability:
        if name in self.passabilities:
            return self.passabilities[name]
        if name in self.computing_pass or name not in self.structs:
            return MojoPassability.MEMORY_ONLY
        var decl = self.structs[name].copy()
        var result = MojoPassability.MEMORY_ONLY
        if (
            decl.kind == StructKind.PLAIN
            and not decl.flexible_tail
            and not has_atomic_storage(decl)
        ):
            self.computing_pass[name] = True
            result = MojoPassability.TRIVIAL_REGISTER_PASSABLE
            for m in decl.members:
                var p = MojoPassability.TRIVIAL_REGISTER_PASSABLE
                match m:
                    case .stored_member(v):
                        p = self.type_passability(v.type.ptr()[])
                    case .bitfield_group_member(v):
                        p = self.type_passability(v.storage_type.ptr()[])
                    case .opaque_storage_member(_):
                        p = MojoPassability.MEMORY_ONLY
                    case .padding_member(_):
                        pass
                if p == MojoPassability.MEMORY_ONLY:
                    result = MojoPassability.MEMORY_ONLY
                elif (
                    p == MojoPassability.REGISTER_PASSABLE
                    and result == MojoPassability.TRIVIAL_REGISTER_PASSABLE
                ):
                    result = MojoPassability.REGISTER_PASSABLE
            _ = self.computing_pass.pop(name)
        self.passabilities[name] = result
        return result

    def type_transfer(mut self, t: MojoType) raises -> TransferTraits:
        match t:
            case .builtin_type(v):
                return TransferTraits(
                    v.name != MojoBuiltin.UNSUPPORTED, v.name != MojoBuiltin.UNSUPPORTED
                )
            case .mojo_function_ptr(_) | .mojo_pointer(_):
                return TransferTraits(True, True)
            case .mojo_array(v):
                return self.type_transfer(v.element.ptr()[])
            case .parametric_type(v):
                if v.base == ParametricBase.ATOMIC:
                    return TransferTraits(False, False)
                if v.base == ParametricBase.SIMD or v.base == ParametricBase.COMPLEX_SIMD:
                    return TransferTraits(True, True)
                var result = TransferTraits(True, True)
                for arg in v.args:
                    match arg:
                        case .type_arg(a):
                            var traits = self.type_transfer(a.type.ptr()[])
                            result.copyable = result.copyable and traits.copyable
                            result.movable = result.movable and traits.movable
                        case _:
                            pass
                return result^
            case .named_type(v):
                if _trivial_name(v.name):
                    return TransferTraits(True, True)
                if v.name in self.structs:
                    return self.record_transfer(v.name)
                if v.name not in self.aliases:
                    return TransferTraits(False, False)
                var alias = self.aliases[v.name].copy()
                if alias.kind == AliasKind.CALLBACK_SIGNATURE:
                    return TransferTraits(True, True)
                if (
                    alias.kind == AliasKind.TYPE_ALIAS or alias.kind == AliasKind.UNION_LAYOUT
                ) and alias.type_value:
                    return self.type_transfer(alias.type_value.value().ptr()[])
                return TransferTraits(False, False)

    def record_transfer(mut self, name: String) raises -> TransferTraits:
        if name in self.transfers:
            return self.transfers[name].copy()
        if name in self.computing_transfer:
            return TransferTraits(True, True)
        if name not in self.structs:
            return TransferTraits(False, False)
        var decl = self.structs[name].copy()
        var result = TransferTraits(True, True)
        if decl.flexible_tail or has_atomic_storage(decl):
            result = TransferTraits(False, False)
        elif decl.kind == StructKind.PLAIN and not has_opaque_storage(decl):
            self.computing_transfer[name] = True
            for m in decl.members:
                var traits = TransferTraits(True, True)
                match m:
                    case .stored_member(v):
                        traits = self.type_transfer(v.type.ptr()[])
                    case .bitfield_group_member(v):
                        traits = self.type_transfer(v.storage_type.ptr()[])
                    case .opaque_storage_member(_) | .padding_member(_):
                        pass
                result.copyable = result.copyable and traits.copyable
                result.movable = result.movable and traits.movable
            _ = self.computing_transfer.pop(name)
        self.transfers[name] = result.copy()
        return result^

    def assign(mut self, decl: MojoDecl) raises -> MojoDecl:
        match decl:
            case .struct_decl(v):
                var out = v.copy()
                var p = self.record_passability(v.name)
                var transfer = self.record_transfer(v.name)
                out.passability = p
                out.traits = List[StructTraits]()
                if has_atomic_storage(v) or v.flexible_tail:
                    out.traits.append(StructTraits.NOT_MOVABLE)
                    out.fieldwise_init = False
                else:
                    if p == MojoPassability.TRIVIAL_REGISTER_PASSABLE:
                        out.traits.append(StructTraits.TRIVIAL_REGISTER_PASSABLE)
                    elif p == MojoPassability.REGISTER_PASSABLE:
                        out.traits.append(StructTraits.REGISTER_PASSABLE)
                    if transfer.copyable:
                        out.traits.append(StructTraits.COPYABLE)
                    out.traits.append(
                        StructTraits.MOVABLE if transfer.movable else StructTraits.NOT_MOVABLE
                    )
                    out.fieldwise_init = (
                        v.kind == StructKind.PLAIN
                        and not has_opaque_storage(v)
                        and not is_pure_bitfield(v)
                    )
                return MojoDecl.struct_decl(out^)
            case .function_decl(v):
                var out = v.copy()
                if (
                    v.kind == FunctionKind.WRAPPER
                    and self.type_passability(v.return_type.ptr()[]) == MojoPassability.MEMORY_ONLY
                ):
                    out.kind = FunctionKind.NON_REGISTER_RETURN_STUB
                return MojoDecl.function_decl(out^)
            case .alias_decl(_) | .global_decl(_):
                return decl.copy()


def assign_record_policies(module: MojoModule) raises -> MojoModule:
    validate_mojo_module(module)
    var state = _PolicyState(module)
    var result = module.copy()
    result.decls = List[MojoDecl]()
    for d in module.decls:
        result.decls.append(state.assign(d))
    return result^


struct PolicyInferencePass:
    def __init__(out self):
        pass

    def run(self, module: MojoModule) raises -> MojoModule:
        return assign_record_policies(module)
