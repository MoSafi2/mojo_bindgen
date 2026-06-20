"""Normalize MojoIR into a printer-ready module."""

from __future__ import annotations

from dataclasses import dataclass, replace

from mojo_bindgen.analysis.common import _mojo_align_decorator_ok, mojo_ident
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    Array,
    BinaryExpr,
    BitfieldGroupMember,
    BuiltinType,
    CallExpr,
    CallTarget,
    CastExpr,
    CharLiteral,
    ComptimeMember,
    ConstExpr,
    FloatLiteral,
    FunctionDecl,
    FunctionKind,
    FunctionPtr,
    GlobalDecl,
    GlobalKind,
    Initializer,
    InitializerParam,
    IntLiteral,
    LinkMode,
    ModuleDependencies,
    ModuleImport,
    MojoDecl,
    MojoModule,
    NamedType,
    Param,
    ParametricType,
    Pointer,
    RefExpr,
    SizeOfExpr,
    StoredMember,
    StringLiteral,
    StructDecl,
    StructMember,
    SupportDecl,
    SupportDeclKind,
    Type,
    TypeArg,
    UnaryExpr,
)


class NormalizeMojoModuleError(ValueError):
    """Raised when MojoIR normalization cannot produce printer-ready IR."""


@dataclass
class NormalizeMojoModulePass:
    """Resolve printer-facing facts into explicit MojoIR."""

    def run(self, module: MojoModule) -> MojoModule:
        self._module = module
        self._reserved_names = {decl.name for decl in module.decls}
        self._function_signature_names = {
            decl.name
            for decl in module.decls
            if isinstance(decl, AliasDecl) and decl.kind == AliasKind.CALLBACK_SIGNATURE
        }
        self._synth_aliases: list[AliasDecl] = []
        self._synth_aliases_by_path: dict[tuple[str, ...], str] = {}
        self._imports_by_module: dict[str, set[str]] = {}
        self._support_decl_kinds: set[SupportDeclKind] = set()

        normalized_decls = [self._normalize_decl(decl) for decl in module.decls]
        all_decls = [*self._synth_aliases, *self._ordered_decls(normalized_decls)]
        dependencies = self._collect_dependencies(all_decls)

        return replace(
            module,
            dependencies=dependencies,
            decls=all_decls,
        )

    def _normalize_decl(self, decl: MojoDecl) -> MojoDecl:
        if isinstance(decl, StructDecl):
            return replace(
                decl,
                align_decorator=self._resolve_align_decorator(decl),
                members=[self._normalize_member(decl.name, member) for member in decl.members],
                comptime_members=[
                    self._normalize_comptime_member(decl.name, member)
                    for member in decl.comptime_members
                ],
                initializers=[
                    self._normalize_initializer(decl.name, initializer)
                    for initializer in decl.initializers
                ],
            )
        if isinstance(decl, AliasDecl):
            if decl.kind == AliasKind.CALLBACK_SIGNATURE:
                function_type = self._function_type_from_type(decl.type_value)
                if function_type is None:
                    return decl
                return replace(
                    decl,
                    type_value=self._normalize_function_type(function_type, (decl.name,)),
                )
            return replace(
                decl,
                type_value=(
                    None
                    if decl.type_value is None
                    else self._normalize_type(decl.type_value, (decl.name,))
                ),
                const_type=(
                    None
                    if decl.const_type is None
                    else self._normalize_type(decl.const_type, (decl.name, "const_type"))
                ),
                const_value=(
                    None
                    if decl.const_value is None
                    else self._normalize_const_expr(decl.const_value, (decl.name, "const"))
                ),
            )
        if isinstance(decl, FunctionDecl):
            return replace(
                decl,
                params=[
                    Param(
                        name=param.name,
                        type=self._normalize_type(
                            param.type, (decl.name, param.name or f"param{i}")
                        ),
                        doc=param.doc,
                    )
                    for i, param in enumerate(decl.params)
                ],
                return_type=self._normalize_type(decl.return_type, (decl.name, "return")),
                call_target=CallTarget(
                    link_mode=self._effective_link_mode(decl),
                    symbol=decl.call_target.symbol,
                ),
            )
        if isinstance(decl, GlobalDecl):
            return replace(
                decl,
                value_type=self._normalize_type(decl.value_type, (decl.name, "value")),
            )
        raise NormalizeMojoModuleError(f"unsupported MojoDecl node: {type(decl).__name__!r}")

    @staticmethod
    def _resolve_align_decorator(decl: StructDecl) -> int | None:
        if decl.align_decorator is not None:
            return decl.align_decorator
        if decl.align is None:
            return None
        return decl.align if _mojo_align_decorator_ok(decl.align) else None

    def _normalize_member(self, struct_name: str, member: StructMember) -> StructMember:
        if isinstance(member, StoredMember):
            return replace(
                member,
                type=self._normalize_type(member.type, (struct_name, member.name or "field")),
            )
        if isinstance(member, BitfieldGroupMember):
            return replace(
                member,
                storage_type=self._normalize_type(
                    member.storage_type,
                    (struct_name, member.storage_name or "bitfield_storage"),
                ),
                fields=[
                    replace(
                        field,
                        logical_type=self._normalize_type(
                            field.logical_type, (struct_name, field.name or "bitfield")
                        ),
                    )
                    for field in member.fields
                ],
            )
        return member

    def _normalize_initializer(self, struct_name: str, initializer: Initializer) -> Initializer:
        return replace(
            initializer,
            params=[
                InitializerParam(
                    name=param.name,
                    type=self._normalize_type(
                        param.type,
                        (struct_name, param.name or f"init_{i}"),
                    ),
                )
                for i, param in enumerate(initializer.params)
            ],
        )

    def _normalize_comptime_member(
        self,
        struct_name: str,
        member: ComptimeMember,
    ) -> ComptimeMember:
        return replace(
            member,
            type_value=(
                None
                if member.type_value is None
                else self._normalize_type(member.type_value, (struct_name, member.name, "type"))
            ),
            const_value=(
                None
                if member.const_value is None
                else self._normalize_const_expr(
                    member.const_value, (struct_name, member.name, "const")
                )
            ),
        )

    def _normalize_type(
        self,
        t: Type,
        context: tuple[str, ...],
        *,
        allow_inline_function: bool = False,
    ) -> Type:
        if isinstance(t, BuiltinType):
            return t
        if isinstance(t, NamedType):
            return t
        if isinstance(t, Pointer):
            return replace(
                t,
                pointee=(
                    None
                    if t.pointee is None
                    else self._normalize_type(t.pointee, (*context, "pointee"))
                ),
            )
        if isinstance(t, Array):
            return replace(t, element=self._normalize_type(t.element, (*context, "element")))
        if isinstance(t, ParametricType):
            return replace(
                t,
                args=[
                    (
                        replace(
                            arg,
                            type=self._normalize_type(arg.type, (*context, f"arg{i}")),
                        )
                        if isinstance(arg, TypeArg)
                        else arg
                    )
                    for i, arg in enumerate(t.args)
                ],
            )
        function_type = self._function_type_from_type(t)
        if function_type is not None:
            normalized = self._normalize_function_type(function_type, context)
            if allow_inline_function:
                return normalized
            alias_name = self._ensure_function_alias(context, normalized)
            return NamedType(alias_name)
        raise NormalizeMojoModuleError(f"unsupported Type node: {type(t).__name__!r}")

    def _normalize_function_type(
        self, function_type: FunctionPtr, context: tuple[str, ...]
    ) -> FunctionPtr:
        return replace(
            function_type,
            params=[
                Param(
                    name=param.name,
                    type=self._normalize_type(
                        param.type,
                        (*context, param.name or f"arg{i}"),
                    ),
                )
                for i, param in enumerate(function_type.params)
            ],
            ret=self._normalize_type(function_type.ret, (*context, "return")),
        )

    def _normalize_const_expr(self, expr: ConstExpr, context: tuple[str, ...]) -> ConstExpr:
        if isinstance(
            expr,
            (
                IntLiteral,
                FloatLiteral,
                StringLiteral,
                CharLiteral,
                RefExpr,
            ),
        ):
            return expr
        if isinstance(expr, UnaryExpr):
            return replace(
                expr,
                operand=self._normalize_const_expr(expr.operand, (*context, "operand")),
            )
        if isinstance(expr, BinaryExpr):
            return replace(
                expr,
                lhs=self._normalize_const_expr(expr.lhs, (*context, "lhs")),
                rhs=self._normalize_const_expr(expr.rhs, (*context, "rhs")),
            )
        if isinstance(expr, CastExpr):
            return replace(
                expr,
                target=self._normalize_type(expr.target, (*context, "cast_target")),
                expr=self._normalize_const_expr(expr.expr, (*context, "cast_expr")),
            )
        if isinstance(expr, CallExpr):
            return replace(
                expr,
                callee=self._normalize_const_expr(expr.callee, (*context, "callee")),
                args=[
                    self._normalize_const_expr(arg, (*context, f"arg{i}"))
                    for i, arg in enumerate(expr.args)
                ],
            )
        if isinstance(expr, SizeOfExpr):
            return replace(
                expr,
                target=self._normalize_type(expr.target, (*context, "sizeof_target")),
            )
        raise NormalizeMojoModuleError(f"unsupported ConstExpr node: {type(expr).__name__!r}")

    def _ensure_function_alias(
        self,
        path: tuple[str, ...],
        function_type: FunctionPtr,
    ) -> str:
        existing = self._synth_aliases_by_path.get(path)
        if existing is not None:
            return existing

        logical_parts = [part for part in path if part]
        while logical_parts and logical_parts[-1] in {
            "callback",
            "signature",
            "pointee",
            "element",
        }:
            logical_parts.pop()
        base = mojo_ident("_".join(logical_parts), fallback="callback")
        if not base.endswith("_cb"):
            base = f"{base}_cb"
        name = base
        suffix = 2
        while name in self._reserved_names:
            name = f"{base}_{suffix}"
            suffix += 1
        self._reserved_names.add(name)
        self._function_signature_names.add(name)

        self._synth_aliases_by_path[path] = name
        self._synth_aliases.append(
            AliasDecl(
                name=name,
                kind=AliasKind.CALLBACK_SIGNATURE,
                type_value=function_type,
            )
        )
        return name

    def _collect_dependencies(self, decls: list[MojoDecl]) -> ModuleDependencies:
        self._seed_dependencies(self._module.dependencies)

        for decl in decls:
            if isinstance(decl, FunctionDecl) and decl.kind == FunctionKind.WRAPPER:
                if decl.call_target.link_mode == LinkMode.OWNED_DL_HANDLE:
                    self._record_support_decl(SupportDeclKind.DL_HANDLE_HELPERS)
            elif isinstance(decl, GlobalDecl) and decl.kind == GlobalKind.WRAPPER:
                self._record_support_decl(SupportDeclKind.GLOBAL_SYMBOL_HELPERS)
                self._record_support_decl(SupportDeclKind.DL_HANDLE_HELPERS)

        if SupportDeclKind.DL_HANDLE_HELPERS in self._support_decl_kinds:
            ffi_imports = ["OwnedDLHandle", "_DLHandle", "_Global", "_get_global"]
            if self._module.link_mode == LinkMode.EXTERNAL_CALL:
                ffi_imports.append("DEFAULT_RTLD")
            else:
                ffi_imports.append("_find_dylib")
            self._record_import("std.ffi", *ffi_imports)
            self._record_import("std.memory.unsafe_pointer", "unsafe_cast")
            os_imports = ["abort"]
            if self._module.link_mode == LinkMode.OWNED_DL_HANDLE:
                os_imports.append("getenv")
                self._record_import("std.pathlib", "Path")
            self._record_import("std.os", *os_imports)

        for decl in decls:
            if isinstance(decl, FunctionDecl) and decl.kind == FunctionKind.WRAPPER:
                if decl.call_target.link_mode == LinkMode.EXTERNAL_CALL:
                    self._record_import("std.ffi", "external_call")
            self._collect_decl_imports(
                decl,
            )

        if self._module.link_mode == LinkMode.EXTERNAL_CALL and any(
            not isinstance(decl, AliasDecl) for decl in decls
        ):
            self._record_import("std.ffi", "external_call")

        return ModuleDependencies(
            imports=self._ordered_imports(),
            support_decls=self._ordered_support_decls(),
        )

    def _ordered_imports(self) -> list[ModuleImport]:
        imports: list[ModuleImport] = []
        ffi_names = self._imports_by_module.get("std.ffi", set())
        ordered_ffi: list[str] = []
        if "external_call" in ffi_names:
            ordered_ffi.append("external_call")
        if "DEFAULT_RTLD" in ffi_names:
            ordered_ffi.append("DEFAULT_RTLD")
        if "OwnedDLHandle" in ffi_names:
            ordered_ffi.append("OwnedDLHandle")
        for private_name in ("_DLHandle", "_Global", "_find_dylib", "_get_global"):
            if private_name in ffi_names:
                ordered_ffi.append(private_name)
        if "UnsafeUnion" in ffi_names:
            ordered_ffi.append("UnsafeUnion")
        ordered_ffi.extend(sorted(name for name in ffi_names if name.startswith("c_")))
        ordered_ffi.extend(
            sorted(
                name
                for name in ffi_names
                if name not in set(ordered_ffi) and not name.startswith("c_")
            )
        )
        if ordered_ffi:
            imports.append(ModuleImport(module="std.ffi", names=ordered_ffi))
        preferred_modules = (
            "std.sys.info",
            "std.memory",
            "std.builtin.simd",
            "std.complex",
            "std.atomic",
        )
        for module_name in preferred_modules:
            names = self._imports_by_module.get(module_name)
            if names:
                imports.append(ModuleImport(module=module_name, names=sorted(names)))
        for module_name in sorted(
            name for name in self._imports_by_module if name not in {"std.ffi", *preferred_modules}
        ):
            imports.append(
                ModuleImport(module=module_name, names=sorted(self._imports_by_module[module_name]))
            )
        return imports

    def _ordered_support_decls(self) -> list[SupportDecl]:
        ordered: list[SupportDecl] = []
        for kind in (
            SupportDeclKind.DL_HANDLE_HELPERS,
            SupportDeclKind.GLOBAL_SYMBOL_HELPERS,
        ):
            if kind in self._support_decl_kinds:
                ordered.append(SupportDecl(kind))
        return ordered

    def _collect_decl_imports(
        self,
        decl: MojoDecl,
    ) -> None:
        if isinstance(decl, StructDecl):
            for member in decl.members:
                if isinstance(member, StoredMember):
                    self._collect_type_imports(member.type)
                elif isinstance(member, BitfieldGroupMember):
                    self._record_import("std.sys.info", "is_big_endian", "is_little_endian")
                    self._collect_type_imports(member.storage_type)
                    for field in member.fields:
                        self._collect_type_imports(field.logical_type)
            for member in decl.comptime_members:
                if member.type_value is not None:
                    self._collect_type_imports(member.type_value)
                if member.const_value is not None:
                    self._collect_const_expr_imports(member.const_value)
            for initializer in decl.initializers:
                for param in initializer.params:
                    self._collect_type_imports(param.type)
        elif isinstance(decl, AliasDecl):
            if decl.type_value is not None:
                self._collect_type_imports(decl.type_value)
            if decl.const_type is not None:
                self._collect_type_imports(decl.const_type)
            if decl.const_value is not None:
                self._collect_const_expr_imports(decl.const_value)
        elif isinstance(decl, FunctionDecl):
            self._collect_type_imports(decl.return_type)
            for param in decl.params:
                self._collect_type_imports(param.type)
        elif isinstance(decl, GlobalDecl):
            self._collect_type_imports(decl.value_type)

    def _collect_const_expr_imports(
        self,
        expr: ConstExpr,
    ) -> None:
        if isinstance(
            expr,
            (
                IntLiteral,
                FloatLiteral,
                StringLiteral,
                CharLiteral,
                RefExpr,
            ),
        ):
            return
        if isinstance(expr, UnaryExpr):
            self._collect_const_expr_imports(expr.operand)
            return
        if isinstance(expr, BinaryExpr):
            self._collect_const_expr_imports(expr.lhs)
            self._collect_const_expr_imports(expr.rhs)
            return
        if isinstance(expr, CastExpr):
            self._collect_type_imports(expr.target)
            self._collect_const_expr_imports(expr.expr)
            return
        if isinstance(expr, CallExpr):
            self._collect_const_expr_imports(expr.callee)
            for arg in expr.args:
                self._collect_const_expr_imports(arg)
            return
        if isinstance(expr, SizeOfExpr):
            self._record_import("std.sys.info", "size_of")
            self._collect_type_imports(expr.target)
            return

    def _collect_type_imports(self, t: Type) -> None:
        if isinstance(t, BuiltinType):
            if t.name.value.startswith("c_"):
                self._record_import("std.ffi", t.name.value)
            return
        if isinstance(t, NamedType):
            return
        if isinstance(t, Pointer):
            if t.pointee is None:
                self._record_import("std.memory", "ImmutOpaquePointer", "MutOpaquePointer")
            else:
                self._collect_type_imports(t.pointee)
            return
        if isinstance(t, Array):
            self._collect_type_imports(t.element)
            return
        if isinstance(t, ParametricType):
            if t.base.value == "SIMD":
                self._record_import("std.builtin.simd", "SIMD")
            elif t.base.value == "ComplexSIMD":
                self._record_import("std.complex", "ComplexSIMD")
            elif t.base.value == "Atomic":
                self._record_import("std.atomic", "Atomic")
            elif t.base.value == "UnsafeUnion":
                self._record_import("std.ffi", "UnsafeUnion")
            for arg in t.args:
                if isinstance(arg, TypeArg):
                    self._collect_type_imports(arg.type)
            return
        if isinstance(t, FunctionPtr):
            for param in t.params:
                self._collect_type_imports(param.type)
            self._collect_type_imports(t.ret)
            return
        raise NormalizeMojoModuleError(f"unsupported Type node: {type(t).__name__!r}")

    def _seed_dependencies(self, dependencies: ModuleDependencies) -> None:
        for imp in dependencies.imports:
            self._record_import(imp.module, *imp.names)
        for support in dependencies.support_decls:
            self._record_support_decl(support.kind)

    def _record_import(self, module: str, *names: str) -> None:
        if not names:
            return
        self._imports_by_module.setdefault(module, set()).update(names)

    def _record_support_decl(self, kind: SupportDeclKind) -> None:
        self._support_decl_kinds.add(kind)

    def _effective_link_mode(self, decl: FunctionDecl) -> LinkMode:
        if (
            decl.call_target.link_mode == LinkMode.EXTERNAL_CALL
            and not decl.call_target.symbol
            and self._module.link_mode != LinkMode.EXTERNAL_CALL
        ):
            return self._module.link_mode
        return decl.call_target.link_mode

    @staticmethod
    def _function_type_from_type(t: Type | None) -> FunctionPtr | None:
        if t is None:
            return None
        if isinstance(t, FunctionPtr):
            return t
        return None

    @staticmethod
    def _ordered_decls(decls: list[MojoDecl]) -> list[MojoDecl]:
        def sort_key(decl: MojoDecl) -> tuple[int, int]:
            if isinstance(decl, AliasDecl):
                rank = 0
            elif isinstance(decl, StructDecl):
                rank = 1
            elif isinstance(decl, GlobalDecl):
                rank = 2
            else:
                rank = 3
            return rank, 0

        return sorted(decls, key=sort_key)


def normalize_mojo_module(module: MojoModule) -> MojoModule:
    """Normalize MojoIR into a form the printer can emit directly."""

    return NormalizeMojoModulePass().run(module)


__all__ = [
    "NormalizeMojoModuleError",
    "NormalizeMojoModulePass",
    "normalize_mojo_module",
]
