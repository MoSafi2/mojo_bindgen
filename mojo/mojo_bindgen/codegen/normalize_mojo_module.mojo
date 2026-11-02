"""Resolve callback names, dependency ordering and all printer-facing target facts."""
from std.memory import ArcPointer
from ..ir import *
from ..analysis.traversal import validate_mojo_module
from ..analysis.mojo.physical_members import physical_members
from ..analysis.mojo.validate_finalized import validate_finalized_mojo_module
from ..analysis.common import mojo_ident, mojo_align_decorator_ok, sort_strings


def _decl_name(d: MojoDecl) -> String:
    match d:
        case .struct_decl(v):
            return v.name.copy()
        case .alias_decl(v):
            return v.name.copy()
        case .function_decl(v):
            return v.name.copy()
        case .global_decl(v):
            return v.name.copy()


def _path(path: List[String], part: String) -> List[String]:
    var result = path.copy()
    result.append(part.copy())
    return result^


def _key(path: List[String]) -> String:
    var result = String()
    for p in path:
        result += String(p.byte_length()) + ":" + p
    return result^


struct _NormalizeState(Movable):
    var module: MojoModule
    var reserved: Dict[String, Bool]
    var storage_decls: List[StructDecl]
    var storage_names: Dict[String, String]
    var aliases: List[AliasDecl]
    var aliases_by_path: Dict[String, String]
    var imports: Dict[String, Dict[String, Bool]]
    var supports: Dict[String, Bool]

    def __init__(out self, module: MojoModule):
        self.module = module.copy()
        self.reserved = Dict[String, Bool]()
        self.storage_decls = List[StructDecl]()
        self.storage_names = Dict[String, String]()
        self.aliases = List[AliasDecl]()
        self.aliases_by_path = Dict[String, String]()
        self.imports = Dict[String, Dict[String, Bool]]()
        self.supports = Dict[String, Bool]()
        for d in module.decls:
            self.reserved[_decl_name(d)] = True

    def _ensure_alias(mut self, path: List[String], function: MojoFunctionPtr) raises -> String:
        var key = _key(path)
        if key in self.aliases_by_path:
            return self.aliases_by_path[key].copy()
        var logical = List[String]()
        for p in path:
            if p.byte_length():
                logical.append(p.copy())
        while len(logical):
            var last = logical[len(logical) - 1].copy()
            if (
                last != "callback"
                and last != "signature"
                and last != "pointee"
                and last != "element"
            ):
                break
            _ = logical.pop()
        var raw = String()
        for i in range(len(logical)):
            if i:
                raw += "_"
            raw += logical[i]
        var base = mojo_ident(raw, "callback")
        if not base.endswith("_cb"):
            base += "_cb"
        var name = base.copy()
        var suffix = 2
        while name in self.reserved:
            name = base + "_" + String(suffix)
            suffix += 1
        self.reserved[name] = True
        self.aliases_by_path[key] = name.copy()
        self.aliases.append(
            AliasDecl(
                name.copy(),
                AliasKind.CALLBACK_SIGNATURE,
                type_value=ArcPointer(MojoType.mojo_function_ptr(function.copy())),
            )
        )
        return name^

    def storage_type(mut self, v: OpaqueStorageType) raises -> MojoType:
        if (
            v.size_bytes <= 0
            or v.align_bytes <= 0
            or (v.align_bytes & (v.align_bytes - 1)) != 0
            or v.align_bytes > (1 << 29)
            or v.size_bytes % v.align_bytes
        ):
            raise Error("invalid opaque storage geometry")
        var key = String(v.size_bytes) + "_" + String(v.align_bytes)
        if key not in self.storage_names:
            var base = "_bindgen_storage_" + key
            var name = base.copy()
            var suffix = 2
            while name in self.reserved:
                name = base + "_" + String(suffix)
                suffix += 1
            self.reserved[name] = True
            self.storage_names[key] = name.copy()
            var decl = StructDecl(name, align=v.align_bytes, align_decorator=v.align_bytes)
            decl.traits = [StructTraits.COPYABLE, StructTraits.MOVABLE]
            decl.members.append(
                StructMember.opaque_storage_member(OpaqueStorageMember("storage", v.size_bytes))
            )
            self.storage_decls.append(decl^)
        return MojoType.named_type(NamedType(self.storage_names[key].copy()))

    def function_type(
        mut self, value: MojoFunctionPtr, path: List[String]
    ) raises -> MojoFunctionPtr:
        var out = value.copy()
        out.params = List[MojoParam]()
        for i in range(len(value.params)):
            var p = value.params[i].copy()
            var part = p.name.copy() if p.name.byte_length() else String("arg" + String(i))
            out.params.append(
                MojoParam(p.name.copy(), ArcPointer(self.type(p.type.ptr()[], _path(path, part))))
            )
        out.ret = ArcPointer(self.type(value.ret.ptr()[], _path(path, "return")))
        return out^

    def type(mut self, t: MojoType, path: List[String]) raises -> MojoType:
        match t:
            case .opaque_storage_type(v):
                return self.storage_type(v)
            case .builtin_type(_) | .named_type(_):
                return t.copy()
            case .mojo_pointer(v):
                var out = v.copy()
                if v.pointee:
                    out.pointee = ArcPointer(
                        self.type(v.pointee.value().ptr()[], _path(path, "pointee"))
                    )
                return MojoType.mojo_pointer(out^)
            case .mojo_array(v):
                return MojoType.mojo_array(
                    MojoArray(
                        ArcPointer(self.type(v.element.ptr()[], _path(path, "element"))), v.size
                    )
                )
            case .parametric_type(v):
                var out = v.copy()
                for i in range(len(v.args)):
                    match v.args[i]:
                        case .type_arg(a):
                            out.args[i] = ParametricArg.type_arg(
                                TypeArg(
                                    ArcPointer(
                                        self.type(a.type.ptr()[], _path(path, "arg" + String(i)))
                                    )
                                )
                            )
                        case _:
                            pass
                return MojoType.parametric_type(out^)
            case .mojo_function_ptr(v):
                var normalized = self.function_type(v, path)
                return MojoType.named_type(NamedType(self._ensure_alias(path, normalized)))

    def expr(mut self, value: MojoConstExpr, path: List[String]) raises -> MojoConstExpr:
        match value:
            case .int_literal(_) | .mojo_float_literal(_) | .string_literal(_) | .char_literal(
                _
            ) | .mojo_ref_expr(_):
                return value.copy()
            case .mojo_unary_expr(v):
                return MojoConstExpr.mojo_unary_expr(
                    MojoUnaryExpr(
                        v.op.copy(),
                        ArcPointer(self.expr(v.operand.ptr()[], _path(path, "operand"))),
                    )
                )
            case .mojo_binary_expr(v):
                return MojoConstExpr.mojo_binary_expr(
                    MojoBinaryExpr(
                        v.op.copy(),
                        ArcPointer(self.expr(v.lhs.ptr()[], _path(path, "lhs"))),
                        ArcPointer(self.expr(v.rhs.ptr()[], _path(path, "rhs"))),
                    )
                )
            case .mojo_cast_expr(v):
                return MojoConstExpr.mojo_cast_expr(
                    MojoCastExpr(
                        ArcPointer(self.type(v.target.ptr()[], _path(path, "cast_target"))),
                        ArcPointer(self.expr(v.expr.ptr()[], _path(path, "cast_expr"))),
                    )
                )
            case .mojo_size_of_expr(v):
                return MojoConstExpr.mojo_size_of_expr(
                    MojoSizeOfExpr(
                        ArcPointer(self.type(v.target.ptr()[], _path(path, "sizeof_target")))
                    )
                )
            case .mojo_call_expr(v):
                var callee = ArcPointer(self.expr(v.callee.ptr()[], _path(path, "callee")))
                var args = List[ArcPointer[MojoConstExpr]]()
                for i in range(len(v.args)):
                    args.append(
                        ArcPointer(self.expr(v.args[i].ptr()[], _path(path, "arg" + String(i))))
                    )
                return MojoConstExpr.mojo_call_expr(MojoCallExpr(callee^, args^))

    def decl(mut self, decl: MojoDecl) raises -> MojoDecl:
        var name = _decl_name(decl)
        var path = List[String]()
        path.append(name.copy())
        match decl:
            case .alias_decl(v):
                var out = v.copy()
                if v.kind == AliasKind.CALLBACK_SIGNATURE:
                    if v.type_value:
                        match v.type_value.value().ptr()[]:
                            case .mojo_function_ptr(f):
                                out.type_value = ArcPointer(
                                    MojoType.mojo_function_ptr(self.function_type(f, path))
                                )
                            case _:
                                pass
                    return MojoDecl.alias_decl(out^)
                if v.type_value:
                    out.type_value = ArcPointer(self.type(v.type_value.value().ptr()[], path))
                if v.const_type:
                    out.const_type = ArcPointer(
                        self.type(v.const_type.value().ptr()[], _path(path, "const_type"))
                    )
                if v.const_value:
                    out.const_value = ArcPointer(
                        self.expr(v.const_value.value().ptr()[], _path(path, "const"))
                    )
                return MojoDecl.alias_decl(out^)
            case .function_decl(v):
                var out = v.copy()
                for i in range(len(v.params)):
                    var p = v.params[i].copy()
                    var part = p.name.copy() if p.name.byte_length() else String(
                        "param" + String(i)
                    )
                    out.params[i].type = ArcPointer(self.type(p.type.ptr()[], _path(path, part)))
                out.return_type = ArcPointer(
                    self.type(v.return_type.ptr()[], _path(path, "return"))
                )
                if (
                    v.call_target.link_mode == LinkMode.EXTERNAL_CALL
                    and not v.call_target.symbol.byte_length()
                    and self.module.link_mode != LinkMode.EXTERNAL_CALL
                ):
                    out.call_target.link_mode = self.module.link_mode
                return MojoDecl.function_decl(out^)
            case .global_decl(v):
                var out = v.copy()
                out.value_type = ArcPointer(self.type(v.value_type.ptr()[], _path(path, "value")))
                return MojoDecl.global_decl(out^)
            case .struct_decl(v):
                var out = v.copy()
                out.members = physical_members(v)
                if not v.align_decorator and v.align and mojo_align_decorator_ok(v.align.value()):
                    out.align_decorator = v.align
                for i in range(len(out.members)):
                    match out.members[i]:
                        case .stored_member(m):
                            var member = m.copy()
                            member.type = ArcPointer(
                                self.type(
                                    m.type.ptr()[],
                                    _path(
                                        path, m.name if m.name.byte_length() else String("field")
                                    ),
                                )
                            )
                            out.members[i] = StructMember.stored_member(member^)
                        case .bitfield_group_member(m):
                            var member = m.copy()
                            member.storage_type = ArcPointer(
                                self.type(
                                    m.storage_type.ptr()[],
                                    _path(
                                        path,
                                        m.storage_name if m.storage_name.byte_length() else String(
                                            "bitfield_storage"
                                        ),
                                    ),
                                )
                            )
                            for j in range(len(m.fields)):
                                var f = m.fields[j].copy()
                                member.fields[j].logical_type = ArcPointer(
                                    self.type(
                                        f.logical_type.ptr()[],
                                        _path(
                                            path,
                                            f.name if f.name.byte_length() else String("bitfield"),
                                        ),
                                    )
                                )
                            out.members[i] = StructMember.bitfield_group_member(member^)
                        case .padding_member(_) | .opaque_storage_member(_):
                            pass
                for i in range(len(v.comptime_members)):
                    var m = v.comptime_members[i].copy()
                    var mpath = _path(path, m.name)
                    if m.type_value:
                        out.comptime_members[i].type_value = ArcPointer(
                            self.type(m.type_value.value().ptr()[], _path(mpath, "type"))
                        )
                    if m.const_value:
                        out.comptime_members[i].const_value = ArcPointer(
                            self.expr(m.const_value.value().ptr()[], _path(mpath, "const"))
                        )
                for i in range(len(v.initializers)):
                    for j in range(len(v.initializers[i].params)):
                        var p = v.initializers[i].params[j].copy()
                        var part = p.name.copy() if p.name.byte_length() else String(
                            "init_" + String(j)
                        )
                        out.initializers[i].params[j].type = ArcPointer(
                            self.type(p.type.ptr()[], _path(path, part))
                        )
                return MojoDecl.struct_decl(out^)

    def record_import(mut self, module: String, name: String) raises:
        if module not in self.imports:
            self.imports[module] = Dict[String, Bool]()
        self.imports[module][name] = True

    def support(mut self, kind: SupportDeclKind):
        self.supports[kind.value()] = True

    def type_imports(mut self, t: MojoType) raises:
        match t:
            case .opaque_storage_type(_):
                raise Error("unresolved opaque storage dependency")
            case .builtin_type(v):
                var name = v.name.value()
                if name.startswith("c_"):
                    self.record_import("std.ffi", name)
            case .named_type(_):
                pass
            case .mojo_pointer(v):
                if v.pointee:
                    self.type_imports(v.pointee.value().ptr()[])
            case .mojo_array(v):
                self.type_imports(v.element.ptr()[])
            case .parametric_type(v):
                match v.base:
                    case .SIMD:
                        self.record_import("std.simd", "SIMD")
                    case .COMPLEX_SIMD:
                        self.record_import("std.complex", "ComplexSIMD")
                    case .ATOMIC:
                        self.record_import("std.atomic", "Atomic")
                    case .UNSAFE_UNION:
                        self.record_import("std.ffi", "UnsafeUnion")
                for arg in v.args:
                    match arg:
                        case .type_arg(a):
                            self.type_imports(a.type.ptr()[])
                        case _:
                            pass
            case .mojo_function_ptr(v):
                for p in v.params:
                    self.type_imports(p.type.ptr()[])
                self.type_imports(v.ret.ptr()[])

    def expr_imports(mut self, e: MojoConstExpr) raises:
        match e:
            case .int_literal(_) | .mojo_float_literal(_) | .string_literal(_) | .char_literal(
                _
            ) | .mojo_ref_expr(_):
                pass
            case .mojo_unary_expr(v):
                self.expr_imports(v.operand.ptr()[])
            case .mojo_binary_expr(v):
                self.expr_imports(v.lhs.ptr()[])
                self.expr_imports(v.rhs.ptr()[])
            case .mojo_cast_expr(v):
                self.type_imports(v.target.ptr()[])
                self.expr_imports(v.expr.ptr()[])
            case .mojo_size_of_expr(v):
                self.record_import("std.sys.info", "size_of")
                self.type_imports(v.target.ptr()[])
            case .mojo_call_expr(v):
                self.expr_imports(v.callee.ptr()[])
                for a in v.args:
                    self.expr_imports(a.ptr()[])

    def decl_imports(mut self, d: MojoDecl) raises:
        match d:
            case .struct_decl(v):
                for m in v.members:
                    match m:
                        case .stored_member(f):
                            self.type_imports(f.type.ptr()[])
                        case .bitfield_group_member(g):
                            self.record_import("std.sys.info", "Endian")
                            self.type_imports(g.storage_type.ptr()[])
                            for f in g.fields:
                                self.type_imports(f.logical_type.ptr()[])
                        case _:
                            pass
                for m in v.comptime_members:
                    if m.type_value:
                        self.type_imports(m.type_value.value().ptr()[])
                    if m.const_value:
                        self.expr_imports(m.const_value.value().ptr()[])
                for initializer in v.initializers:
                    for p in initializer.params:
                        self.type_imports(p.type.ptr()[])
            case .alias_decl(v):
                if v.type_value:
                    self.type_imports(v.type_value.value().ptr()[])
                if v.const_type:
                    self.type_imports(v.const_type.value().ptr()[])
                if v.const_value:
                    self.expr_imports(v.const_value.value().ptr()[])
            case .function_decl(v):
                self.type_imports(v.return_type.ptr()[])
                for p in v.params:
                    self.type_imports(p.type.ptr()[])
            case .global_decl(v):
                self.type_imports(v.value_type.ptr()[])

    def dependencies(
        mut self, decls: List[MojoDecl], compatibility_imports: Bool = True
    ) raises -> ModuleDependencies:
        var seeded = self.module.dependencies.copy()
        for imp in seeded.imports:
            for name in imp.names:
                self.record_import(imp.module, name)
        for s in seeded.support_decls:
            self.support(s.kind)
        for d in decls:
            match d:
                case .function_decl(v):
                    if v.kind == FunctionKind.WRAPPER:
                        if v.num_fixed_args:
                            self.support(SupportDeclKind.VARIADIC_HELPERS)
                            self.record_import("std.reflection", "reflect")
                            self.record_import("std.os", "abort")
                            for name in [
                                "c_int",
                                "c_uint",
                                "c_long",
                                "c_ulong",
                                "c_long_long",
                                "c_ulong_long",
                                "c_double",
                            ]:
                                self.record_import("std.ffi", name)
                        if v.call_target.link_mode == LinkMode.OWNED_DL_HANDLE:
                            self.support(SupportDeclKind.DL_HANDLE_HELPERS)
                case .global_decl(v):
                    if v.kind == GlobalKind.WRAPPER:
                        self.support(SupportDeclKind.GLOBAL_SYMBOL_HELPERS)
                        self.support(SupportDeclKind.DL_HANDLE_HELPERS)
                case _:
                    pass
        if SupportDeclKind.DL_HANDLE_HELPERS.value() in self.supports:
            self.record_import("std.ffi", "OwnedDLHandle")
            self.record_import("std.ffi", "_Global")
            self.record_import("std.os", "abort")
            if self.module.link_mode == LinkMode.OWNED_DL_HANDLE:
                self.record_import("std.os", "getenv")
                self.record_import("std.pathlib", "Path")
                self.record_import("std.sys.info", "CompilationTarget")
                self.record_import("std.sys.info", "platform_map")
        var external = False
        for d in decls:
            match d:
                case .function_decl(v):
                    if (
                        v.kind == FunctionKind.WRAPPER
                        and v.call_target.link_mode == LinkMode.EXTERNAL_CALL
                    ):
                        self.record_import("std.ffi", "external_call")
                    if v.kind != FunctionKind.DIRECTIVE_STUB:
                        external = True
                case .alias_decl(_):
                    pass
                case _:
                    external = True
            self.decl_imports(d)
        if compatibility_imports and external and self.module.link_mode == LinkMode.EXTERNAL_CALL:
            self.record_import("std.ffi", "external_call")
        var result = ModuleDependencies()
        var ffi = List[String]()
        if "std.ffi" in self.imports:
            var used = Dict[String, Bool]()
            var names = self.imports["std.ffi"].copy()
            for n in ["external_call", "DEFAULT_RTLD", "OwnedDLHandle", "_Global", "UnsafeUnion"]:
                if n in names:
                    ffi.append(n.copy())
                    used[n] = True
            var c_names = List[String]()
            var rest = List[String]()
            for n in names:
                if n.startswith("c_"):
                    c_names.append(n.copy())
                elif n not in used:
                    rest.append(n.copy())
            sort_strings(c_names)
            sort_strings(rest)
            ffi.extend(c_names^)
            ffi.extend(rest^)
        if len(ffi):
            result.imports.append(ModuleImport("std.ffi", ffi^))
        var done = Dict[String, Bool]()
        done["std.ffi"] = True
        for module in [
            "std.sys.info",
            "std.memory",
            "std.builtin.simd",
            "std.complex",
            "std.atomic",
        ]:
            done[module] = True
            if module in self.imports:
                var names = List[String]()
                for n in self.imports[module]:
                    names.append(n.copy())
                sort_strings(names)
                if len(names):
                    result.imports.append(ModuleImport(module.copy(), names^))
        var modules = List[String]()
        for module in self.imports:
            if module not in done:
                modules.append(module.copy())
        sort_strings(modules)
        for module in modules:
            var names = List[String]()
            for n in self.imports[module]:
                names.append(n.copy())
            sort_strings(names)
            result.imports.append(ModuleImport(module.copy(), names^))
        for kind in [
            SupportDeclKind.DL_HANDLE_HELPERS,
            SupportDeclKind.GLOBAL_SYMBOL_HELPERS,
            SupportDeclKind.VARIADIC_HELPERS,
        ]:
            if kind.value() in self.supports:
                result.support_decls.append(SupportDecl(kind))
        return result^


def normalize_mojo_module(module: MojoModule) raises -> MojoModule:
    validate_mojo_module(module)
    var state = _NormalizeState(module)
    var normalized = List[MojoDecl]()
    for d in module.decls:
        normalized.append(state.decl(d))
    var result = module.copy()
    result.decls = List[MojoDecl]()
    for alias in state.aliases:
        result.decls.append(MojoDecl.alias_decl(alias.copy()))
    for storage in state.storage_decls:
        result.decls.append(MojoDecl.struct_decl(storage.copy()))
    for rank in range(4):
        for d in normalized:
            var current: Int
            match d:
                case .alias_decl(_):
                    current = 0
                case .struct_decl(_):
                    current = 1
                case .global_decl(_):
                    current = 2
                case .function_decl(_):
                    current = 3
            if current == rank:
                result.decls.append(d.copy())
    result.dependencies = state.dependencies(result.decls)
    validate_finalized_mojo_module(result, result.dependencies)
    return result^


def required_module_dependencies(module: MojoModule) raises -> ModuleDependencies:
    validate_mojo_module(module)
    var bare = module.copy()
    bare.dependencies = ModuleDependencies()
    var state = _NormalizeState(bare)
    return state.dependencies(module.decls, compatibility_imports=False)


struct NormalizeMojoModulePass:
    def __init__(out self):
        pass

    def run(self, module: MojoModule) raises -> MojoModule:
        return normalize_mojo_module(module)
