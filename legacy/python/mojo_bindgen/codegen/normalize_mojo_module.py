"""Normalize MojoIR into a printer-ready module."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import assert_never

from mojo_bindgen.analysis.common import _mojo_align_decorator_ok, mojo_ident
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    BitfieldGroupMember,
    BuiltinType,
    CallTarget,
    CharLiteral,
    ComptimeMember,
    FunctionDecl,
    FunctionKind,
    GlobalDecl,
    GlobalKind,
    Initializer,
    InitializerParam,
    IntLiteral,
    LinkMode,
    ModuleDependencies,
    ModuleImport,
    MojoArray,
    MojoBinaryExpr,
    MojoCallExpr,
    MojoCastExpr,
    MojoConstExpr,
    MojoDecl,
    MojoFloatLiteral,
    MojoFunctionPtr,
    MojoModule,
    MojoParam,
    MojoPointer,
    MojoRefExpr,
    MojoSizeOfExpr,
    MojoType,
    MojoUnaryExpr,
    NamedType,
    OpaqueStorageMember,
    OpaqueStorageType,
    PaddingMember,
    ParametricType,
    StoredMember,
    StringLiteral,
    StructDecl,
    StructMember,
    StructTraits,
    SupportDecl,
    SupportDeclKind,
    TypeArg,
)


class NormalizeMojoModuleError(ValueError):
    """Raised when MojoIR normalization cannot produce printer-ready IR."""


@dataclass
class NormalizeMojoModulePass:
    """Resolve printer-facing facts into explicit MojoIR."""

    def run(self, module: MojoModule) -> MojoModule:
        self._start(module)

        normalized_decls = [self._normalize_decl(decl) for decl in module.decls]
        all_decls = [
            *self._synth_aliases,
            *self._storage_decls,
            *self._ordered_decls(normalized_decls),
        ]
        dependencies = self._collect_dependencies(all_decls)

        result = replace(
            module,
            dependencies=dependencies,
            decls=tuple(all_decls),
        )

        from mojo_bindgen.analysis.mojo.validate_finalized import validate_finalized_mojo_module

        validate_finalized_mojo_module(result, result.dependencies)
        return result

    def _start(self, module: MojoModule) -> None:
        self._module = module
        self._reserved_names = {decl.name for decl in module.decls}
        self._function_signature_names = {
            decl.name
            for decl in module.decls
            if isinstance(decl, AliasDecl) and decl.kind == AliasKind.CALLBACK_SIGNATURE
        }
        self._storage_names: dict[tuple[int, int], str] = {}
        self._storage_decls: list[StructDecl] = []
        self._synth_aliases: list[AliasDecl] = []
        self._synth_aliases_by_path: dict[tuple[str, ...], str] = {}
        self._imports_by_module: dict[str, set[str]] = {}
        self._support_decl_kinds: set[SupportDeclKind] = set()

    @staticmethod
    def _physical_members(decl: StructDecl) -> tuple[StructMember, ...]:
        names = {
            m.name
            if isinstance(m, (StoredMember, PaddingMember, OpaqueStorageMember))
            else m.storage_name
            for m in decl.members
        }
        out: list[StructMember] = []
        for member in decl.members:
            if not isinstance(member, PaddingMember) or member.storage_width_bytes:
                out.append(member)
                continue
            offset, remaining = member.byte_offset, member.size_bytes
            if remaining < 0:
                raise NormalizeMojoModuleError("negative padding span")
            chunks: list[tuple[int, int]] = []
            while remaining > 0:
                width = next(n for n in (8, 4, 2, 1) if remaining >= n and offset % n == 0)
                chunks.append((offset, width))
                offset += width
                remaining -= width
            for i, (offset, width) in enumerate(chunks):
                base = member.name if len(chunks) == 1 else f"{member.name}_{i}"
                name, suffix = base, 2
                while name in names and name != member.name:
                    name = f"{base}_{suffix}"
                    suffix += 1
                names.add(name)
                out.append(PaddingMember(name, width, offset, width))
        return tuple(out)

    def _normalize_decl(self, decl: MojoDecl) -> MojoDecl:
        if isinstance(decl, StructDecl):
            return replace(
                decl,
                align_decorator=self._resolve_align_decorator(decl),
                members=tuple(
                    self._normalize_member(decl.name, member)
                    for member in self._physical_members(decl)
                ),
                comptime_members=tuple(
                    self._normalize_comptime_member(decl.name, member)
                    for member in decl.comptime_members
                ),
                initializers=tuple(
                    self._normalize_initializer(decl.name, initializer)
                    for initializer in decl.initializers
                ),
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
                params=tuple(
                    (
                        MojoParam(
                            name=param.name,
                            type=self._normalize_type(
                                param.type, (decl.name, param.name or f"param{i}")
                            ),
                            doc=param.doc,
                        )
                        for i, param in enumerate(decl.params)
                    )
                ),
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
        assert_never(decl)

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
                fields=tuple(
                    replace(
                        field,
                        logical_type=self._normalize_type(
                            field.logical_type, (struct_name, field.name or "bitfield")
                        ),
                    )
                    for field in member.fields
                ),
            )
        if isinstance(member, (PaddingMember, OpaqueStorageMember)):
            return member
        assert_never(member)

    def _normalize_initializer(self, struct_name: str, initializer: Initializer) -> Initializer:
        return replace(
            initializer,
            params=tuple(
                (
                    InitializerParam(
                        name=param.name,
                        type=self._normalize_type(
                            param.type, (struct_name, param.name or f"init_{i}")
                        ),
                    )
                    for i, param in enumerate(initializer.params)
                )
            ),
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
        t: MojoType,
        context: tuple[str, ...],
        *,
        allow_inline_function: bool = False,
    ) -> MojoType:
        if isinstance(t, OpaqueStorageType):
            if (
                t.size_bytes <= 0
                or t.align_bytes <= 0
                or t.align_bytes & (t.align_bytes - 1)
                or t.size_bytes % t.align_bytes
                or t.align_bytes > 2**29
            ):
                raise NormalizeMojoModuleError("invalid opaque storage geometry")
            key = (t.size_bytes, t.align_bytes)
            if key not in self._storage_names:
                base = f"_bindgen_storage_{key[0]}_{key[1]}"
                name = base
                suffix = 2
                while name in self._reserved_names:
                    name = f"{base}_{suffix}"
                    suffix += 1
                self._reserved_names.add(name)
                self._storage_names[key] = name
                self._storage_decls.append(
                    StructDecl(
                        name=name,
                        align=t.align_bytes,
                        align_decorator=t.align_bytes,
                        traits=(StructTraits.COPYABLE, StructTraits.MOVABLE),
                        members=(OpaqueStorageMember("storage", t.size_bytes),),
                    )
                )
            return NamedType(self._storage_names[key])
        if isinstance(t, BuiltinType):
            return t
        if isinstance(t, NamedType):
            return t
        if isinstance(t, MojoPointer):
            return replace(
                t,
                pointee=(
                    None
                    if t.pointee is None
                    else self._normalize_type(t.pointee, (*context, "pointee"))
                ),
            )
        if isinstance(t, MojoArray):
            return replace(t, element=self._normalize_type(t.element, (*context, "element")))
        if isinstance(t, ParametricType):
            return replace(
                t,
                args=tuple(
                    (
                        replace(arg, type=self._normalize_type(arg.type, (*context, f"arg{i}")))
                        if isinstance(arg, TypeArg)
                        else arg
                        for i, arg in enumerate(t.args)
                    )
                ),
            )
        if isinstance(t, MojoFunctionPtr):
            normalized = self._normalize_function_type(t, context)
            if allow_inline_function:
                return normalized
            alias_name = self._ensure_function_alias(context, normalized)
            return NamedType(alias_name)
        assert_never(t)

    def _normalize_function_type(
        self, function_type: MojoFunctionPtr, context: tuple[str, ...]
    ) -> MojoFunctionPtr:
        return replace(
            function_type,
            params=tuple(
                (
                    MojoParam(
                        name=param.name,
                        type=self._normalize_type(param.type, (*context, param.name or f"arg{i}")),
                    )
                    for i, param in enumerate(function_type.params)
                )
            ),
            ret=self._normalize_type(function_type.ret, (*context, "return")),
        )

    def _normalize_const_expr(self, expr: MojoConstExpr, context: tuple[str, ...]) -> MojoConstExpr:
        if isinstance(
            expr,
            (
                IntLiteral,
                MojoFloatLiteral,
                StringLiteral,
                CharLiteral,
                MojoRefExpr,
            ),
        ):
            return expr
        if isinstance(expr, MojoUnaryExpr):
            return replace(
                expr,
                operand=self._normalize_const_expr(expr.operand, (*context, "operand")),
            )
        if isinstance(expr, MojoBinaryExpr):
            return replace(
                expr,
                lhs=self._normalize_const_expr(expr.lhs, (*context, "lhs")),
                rhs=self._normalize_const_expr(expr.rhs, (*context, "rhs")),
            )
        if isinstance(expr, MojoCastExpr):
            return replace(
                expr,
                target=self._normalize_type(expr.target, (*context, "cast_target")),
                expr=self._normalize_const_expr(expr.expr, (*context, "cast_expr")),
            )
        if isinstance(expr, MojoCallExpr):
            return replace(
                expr,
                callee=self._normalize_const_expr(expr.callee, (*context, "callee")),
                args=tuple(
                    (
                        self._normalize_const_expr(arg, (*context, f"arg{i}"))
                        for i, arg in enumerate(expr.args)
                    )
                ),
            )
        if isinstance(expr, MojoSizeOfExpr):
            return replace(
                expr,
                target=self._normalize_type(expr.target, (*context, "sizeof_target")),
            )
        assert_never(expr)

    def _ensure_function_alias(
        self,
        path: tuple[str, ...],
        function_type: MojoFunctionPtr,
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

    def _collect_dependencies(
        self, decls: list[MojoDecl], *, compatibility_imports: bool = True
    ) -> ModuleDependencies:
        self._seed_dependencies(self._module.dependencies)

        for decl in decls:
            if isinstance(decl, FunctionDecl) and decl.kind == FunctionKind.WRAPPER:
                if decl.num_fixed_args is not None:
                    self._record_support_decl(SupportDeclKind.VARIADIC_HELPERS)
                    self._record_import("std.reflection", "reflect")
                    self._record_import("std.os", "abort")
                    self._record_import(
                        "std.ffi",
                        "c_int",
                        "c_uint",
                        "c_long",
                        "c_ulong",
                        "c_long_long",
                        "c_ulong_long",
                        "c_double",
                    )
                if decl.call_target.link_mode == LinkMode.OWNED_DL_HANDLE:
                    self._record_support_decl(SupportDeclKind.DL_HANDLE_HELPERS)
            elif isinstance(decl, GlobalDecl) and decl.kind == GlobalKind.WRAPPER:
                self._record_support_decl(SupportDeclKind.GLOBAL_SYMBOL_HELPERS)
                self._record_support_decl(SupportDeclKind.DL_HANDLE_HELPERS)

        if SupportDeclKind.DL_HANDLE_HELPERS in self._support_decl_kinds:
            self._record_import("std.ffi", "OwnedDLHandle", "_Global")
            os_imports = ["abort"]
            if self._module.link_mode == LinkMode.OWNED_DL_HANDLE:
                os_imports.append("getenv")
                self._record_import("std.pathlib", "Path")
                self._record_import("std.sys.info", "CompilationTarget", "platform_map")
            self._record_import("std.os", *os_imports)

        for decl in decls:
            if isinstance(decl, FunctionDecl) and decl.kind == FunctionKind.WRAPPER:
                if decl.call_target.link_mode == LinkMode.EXTERNAL_CALL:
                    self._record_import("std.ffi", "external_call")
            self._collect_decl_imports(
                decl,
            )

        if (
            compatibility_imports
            and self._module.link_mode == LinkMode.EXTERNAL_CALL
            and any(
                not isinstance(decl, AliasDecl)
                and not (
                    isinstance(decl, FunctionDecl) and decl.kind == FunctionKind.DIRECTIVE_STUB
                )
                for decl in decls
            )
        ):
            self._record_import("std.ffi", "external_call")

        return ModuleDependencies(
            imports=tuple(self._ordered_imports()),
            support_decls=tuple(self._ordered_support_decls()),
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
        for private_name in ("_Global",):
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
            imports.append(ModuleImport(module="std.ffi", names=tuple(ordered_ffi)))
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
                imports.append(ModuleImport(module=module_name, names=tuple(sorted(names))))
        for module_name in sorted(
            name for name in self._imports_by_module if name not in {"std.ffi", *preferred_modules}
        ):
            imports.append(
                ModuleImport(
                    module=module_name, names=tuple(sorted(self._imports_by_module[module_name]))
                )
            )
        return imports

    def _ordered_support_decls(self) -> list[SupportDecl]:
        ordered: list[SupportDecl] = []
        for kind in (
            SupportDeclKind.DL_HANDLE_HELPERS,
            SupportDeclKind.GLOBAL_SYMBOL_HELPERS,
            SupportDeclKind.VARIADIC_HELPERS,
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
                    self._record_import("std.sys.info", "Endian")
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
        else:
            assert_never(decl)

    def _collect_const_expr_imports(
        self,
        expr: MojoConstExpr,
    ) -> None:
        if isinstance(
            expr,
            (
                IntLiteral,
                MojoFloatLiteral,
                StringLiteral,
                CharLiteral,
                MojoRefExpr,
            ),
        ):
            return
        if isinstance(expr, MojoUnaryExpr):
            self._collect_const_expr_imports(expr.operand)
            return
        if isinstance(expr, MojoBinaryExpr):
            self._collect_const_expr_imports(expr.lhs)
            self._collect_const_expr_imports(expr.rhs)
            return
        if isinstance(expr, MojoCastExpr):
            self._collect_type_imports(expr.target)
            self._collect_const_expr_imports(expr.expr)
            return
        if isinstance(expr, MojoCallExpr):
            self._collect_const_expr_imports(expr.callee)
            for arg in expr.args:
                self._collect_const_expr_imports(arg)
            return
        if isinstance(expr, MojoSizeOfExpr):
            self._record_import("std.sys.info", "size_of")
            self._collect_type_imports(expr.target)
            return
        assert_never(expr)

    def _collect_type_imports(self, t: MojoType) -> None:
        if isinstance(t, OpaqueStorageType):
            raise NormalizeMojoModuleError("unresolved opaque storage dependency")
        if isinstance(t, BuiltinType):
            if t.name.value.startswith("c_"):
                self._record_import("std.ffi", t.name.value)
            return
        if isinstance(t, NamedType):
            return
        if isinstance(t, MojoPointer):
            if t.pointee is not None:
                self._collect_type_imports(t.pointee)
            return
        if isinstance(t, MojoArray):
            self._collect_type_imports(t.element)
            return
        if isinstance(t, ParametricType):
            if t.base.value == "SIMD":
                self._record_import("std.simd", "SIMD")
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
        if isinstance(t, MojoFunctionPtr):
            for param in t.params:
                self._collect_type_imports(param.type)
            self._collect_type_imports(t.ret)
            return
        assert_never(t)

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
    def _function_type_from_type(t: MojoType | None) -> MojoFunctionPtr | None:
        if t is None:
            return None
        if isinstance(t, MojoFunctionPtr):
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
            elif isinstance(decl, FunctionDecl):
                rank = 3
            else:
                assert_never(decl)
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


def required_module_dependencies(module: MojoModule) -> ModuleDependencies:
    state = NormalizeMojoModulePass()
    state._start(replace(module, dependencies=ModuleDependencies()))
    return state._collect_dependencies(list(module.decls), compatibility_imports=False)
