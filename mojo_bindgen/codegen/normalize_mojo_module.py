"""Normalize MojoIR into a printer-ready module."""

from __future__ import annotations

from dataclasses import dataclass, replace

from mojo_bindgen.analysis.common import _mojo_align_decorator_ok
from mojo_bindgen.codegen.mojo_mapper import mojo_ident
from mojo_bindgen.mojo_ir import (
    AliasDecl,
    AliasKind,
    ArrayType,
    BitfieldGroupMember,
    BuiltinType,
    CallbackParam,
    CallbackType,
    CallTarget,
    EnumDecl,
    FunctionDecl,
    FunctionKind,
    FunctionType,
    GlobalDecl,
    GlobalKind,
    Initializer,
    InitializerParam,
    LinkMode,
    ModuleImport,
    MojoBinaryExpr,
    MojoCastExpr,
    MojoCharLiteral,
    MojoConstExpr,
    MojoDecl,
    MojoFloatLiteral,
    MojoIntLiteral,
    MojoModule,
    MojoRefExpr,
    MojoSizeOfExpr,
    MojoStringLiteral,
    MojoType,
    MojoUnaryExpr,
    NamedType,
    Param,
    ParametricType,
    PointerType,
    StoredMember,
    StructDecl,
    StructMember,
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
        self._module = module
        self._reserved_names = {decl.name for decl in module.decls}
        self._synth_aliases: list[AliasDecl] = []
        self._synth_aliases_by_path: dict[tuple[str, ...], str] = {}
        self._needs_opaque_imports = False
        self._needs_simd_import = False
        self._needs_complex_import = False
        self._needs_atomic_import = False

        normalized_decls = [self._normalize_decl(decl) for decl in module.decls]
        all_decls = [*self._synth_aliases, *normalized_decls]
        support_decls = self._collect_support_decls(all_decls)
        imports = self._collect_imports(all_decls, support_decls)

        return replace(
            module,
            imports=imports,
            support_decls=support_decls,
            decls=all_decls,
        )

    def _normalize_decl(self, decl: MojoDecl) -> MojoDecl:
        if isinstance(decl, StructDecl):
            return replace(
                decl,
                align_decorator=self._resolve_align_decorator(decl),
                members=[self._normalize_member(decl.name, member) for member in decl.members],
                initializers=[
                    self._normalize_initializer(decl.name, initializer)
                    for initializer in decl.initializers
                ],
            )
        if isinstance(decl, EnumDecl):
            return replace(
                decl,
                underlying_type=self._normalize_type(
                    decl.underlying_type, (decl.name, "underlying")
                ),
            )
        if isinstance(decl, AliasDecl):
            if decl.kind == AliasKind.CALLBACK_SIGNATURE:
                callback = self._callback_type_from_type(decl.type_value)
                if callback is None:
                    return decl
                return replace(
                    decl,
                    type_value=self._normalize_callback_type(callback, (decl.name,)),
                )
            return replace(
                decl,
                type_value=(
                    None
                    if decl.type_value is None
                    else self._normalize_type(decl.type_value, (decl.name,))
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

    def _normalize_type(
        self,
        t: MojoType,
        context: tuple[str, ...],
        *,
        allow_inline_callback: bool = False,
    ) -> MojoType:
        if isinstance(t, (BuiltinType, NamedType)):
            return t
        if isinstance(t, PointerType):
            return replace(
                t,
                pointee=(
                    None
                    if t.pointee is None
                    else self._normalize_type(t.pointee, (*context, "pointee"))
                ),
            )
        if isinstance(t, ArrayType):
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
        callback = self._callback_type_from_type(t)
        if callback is not None:
            normalized = self._normalize_callback_type(callback, context)
            if allow_inline_callback:
                return normalized
            alias_name = self._ensure_callback_alias(context, normalized)
            return PointerType(
                pointee=NamedType(alias_name),
                mutability=normalized.mutability,
                origin=normalized.origin,
            )
        raise NormalizeMojoModuleError(f"unsupported MojoType node: {type(t).__name__!r}")

    def _normalize_callback_type(
        self, callback: CallbackType, context: tuple[str, ...]
    ) -> CallbackType:
        return replace(
            callback,
            params=[
                CallbackParam(
                    name=param.name,
                    type=self._normalize_type(
                        param.type,
                        (*context, param.name or f"arg{i}"),
                    ),
                )
                for i, param in enumerate(callback.params)
            ],
            ret=self._normalize_type(callback.ret, (*context, "return")),
        )

    def _normalize_const_expr(self, expr: MojoConstExpr, context: tuple[str, ...]) -> MojoConstExpr:
        if isinstance(
            expr,
            (
                MojoIntLiteral,
                MojoFloatLiteral,
                MojoStringLiteral,
                MojoCharLiteral,
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
        if isinstance(expr, MojoSizeOfExpr):
            return replace(
                expr,
                target=self._normalize_type(expr.target, (*context, "sizeof_target")),
            )
        raise NormalizeMojoModuleError(f"unsupported MojoConstExpr node: {type(expr).__name__!r}")

    def _ensure_callback_alias(
        self,
        path: tuple[str, ...],
        callback: CallbackType,
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

        self._synth_aliases_by_path[path] = name
        self._synth_aliases.append(
            AliasDecl(
                name=name,
                kind=AliasKind.CALLBACK_SIGNATURE,
                type_value=callback,
            )
        )
        return name

    def _collect_support_decls(self, decls: list[MojoDecl]) -> list[SupportDecl]:
        need_dl_helpers = self._module.capabilities.needs_dl_handle_helpers
        need_global_helpers = self._module.capabilities.needs_global_helpers

        for decl in decls:
            if isinstance(decl, FunctionDecl) and decl.kind == FunctionKind.WRAPPER:
                if decl.call_target.link_mode == LinkMode.OWNED_DL_HANDLE:
                    need_dl_helpers = True
            elif isinstance(decl, GlobalDecl) and decl.kind == GlobalKind.WRAPPER:
                need_global_helpers = True
                need_dl_helpers = True

        support_decls: list[SupportDecl] = []
        if need_dl_helpers:
            support_decls.append(SupportDecl(SupportDeclKind.DL_HANDLE_HELPERS))
        if need_global_helpers:
            support_decls.append(SupportDecl(SupportDeclKind.GLOBAL_SYMBOL_HELPERS))
        return support_decls

    def _collect_imports(
        self,
        decls: list[MojoDecl],
        support_decls: list[SupportDecl],
    ) -> list[ModuleImport]:
        ffi_names: set[str] = set()
        needs_opaque_imports = self._module.capabilities.needs_opaque_pointer_types
        needs_simd_import = self._module.capabilities.needs_simd
        needs_complex_import = self._module.capabilities.needs_complex
        needs_atomic_import = self._module.capabilities.needs_atomic

        if self._module.capabilities.needs_unsafe_union:
            ffi_names.add("UnsafeUnion")

        for support in support_decls:
            if support.kind == SupportDeclKind.DL_HANDLE_HELPERS:
                ffi_names.update({"DEFAULT_RTLD", "OwnedDLHandle"})

        for decl in decls:
            if isinstance(decl, FunctionDecl) and decl.kind == FunctionKind.WRAPPER:
                if decl.call_target.link_mode == LinkMode.EXTERNAL_CALL:
                    ffi_names.add("external_call")
            self._collect_decl_imports(
                decl,
                ffi_names=ffi_names,
                mark_opaque=lambda: self._set_flag("opaque"),
                mark_simd=lambda: self._set_flag("simd"),
                mark_complex=lambda: self._set_flag("complex"),
                mark_atomic=lambda: self._set_flag("atomic"),
            )

        needs_opaque_imports = needs_opaque_imports or self._needs_opaque_imports
        needs_simd_import = needs_simd_import or self._needs_simd_import
        needs_complex_import = needs_complex_import or self._needs_complex_import
        needs_atomic_import = needs_atomic_import or self._needs_atomic_import

        imports: list[ModuleImport] = []
        ordered_ffi = []
        if "external_call" in ffi_names:
            ordered_ffi.append("external_call")
        if "DEFAULT_RTLD" in ffi_names:
            ordered_ffi.append("DEFAULT_RTLD")
        if "OwnedDLHandle" in ffi_names:
            ordered_ffi.append("OwnedDLHandle")
        if "UnsafeUnion" in ffi_names:
            ordered_ffi.append("UnsafeUnion")
        ordered_ffi.extend(sorted(name for name in ffi_names if name.startswith("c_")))
        if ordered_ffi:
            imports.append(ModuleImport(module="std.ffi", names=ordered_ffi))
        if needs_opaque_imports:
            imports.append(
                ModuleImport(
                    module="std.memory",
                    names=["ImmutOpaquePointer", "MutOpaquePointer"],
                )
            )
        if needs_simd_import:
            imports.append(ModuleImport(module="std.builtin.simd", names=["SIMD"]))
        if needs_complex_import:
            imports.append(ModuleImport(module="std.complex", names=["ComplexSIMD"]))
        if needs_atomic_import:
            imports.append(ModuleImport(module="std.atomic", names=["Atomic"]))
        return imports

    def _collect_decl_imports(
        self,
        decl: MojoDecl,
        *,
        ffi_names: set[str],
        mark_opaque,
        mark_simd,
        mark_complex,
        mark_atomic,
    ) -> None:
        if isinstance(decl, StructDecl):
            for member in decl.members:
                if isinstance(member, StoredMember):
                    self._collect_type_imports(
                        member.type,
                        ffi_names=ffi_names,
                        mark_opaque=mark_opaque,
                        mark_simd=mark_simd,
                        mark_complex=mark_complex,
                        mark_atomic=mark_atomic,
                    )
                elif isinstance(member, BitfieldGroupMember):
                    self._collect_type_imports(
                        member.storage_type,
                        ffi_names=ffi_names,
                        mark_opaque=mark_opaque,
                        mark_simd=mark_simd,
                        mark_complex=mark_complex,
                        mark_atomic=mark_atomic,
                    )
                    for field in member.fields:
                        self._collect_type_imports(
                            field.logical_type,
                            ffi_names=ffi_names,
                            mark_opaque=mark_opaque,
                            mark_simd=mark_simd,
                            mark_complex=mark_complex,
                            mark_atomic=mark_atomic,
                        )
            for initializer in decl.initializers:
                for param in initializer.params:
                    self._collect_type_imports(
                        param.type,
                        ffi_names=ffi_names,
                        mark_opaque=mark_opaque,
                        mark_simd=mark_simd,
                        mark_complex=mark_complex,
                        mark_atomic=mark_atomic,
                    )
        elif isinstance(decl, EnumDecl):
            self._collect_type_imports(
                decl.underlying_type,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
        elif isinstance(decl, AliasDecl):
            if decl.type_value is not None:
                self._collect_type_imports(
                    decl.type_value,
                    ffi_names=ffi_names,
                    mark_opaque=mark_opaque,
                    mark_simd=mark_simd,
                    mark_complex=mark_complex,
                    mark_atomic=mark_atomic,
                )
            if decl.const_value is not None:
                self._collect_const_expr_imports(
                    decl.const_value,
                    ffi_names=ffi_names,
                    mark_opaque=mark_opaque,
                    mark_simd=mark_simd,
                    mark_complex=mark_complex,
                    mark_atomic=mark_atomic,
                )
        elif isinstance(decl, FunctionDecl):
            self._collect_type_imports(
                decl.return_type,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            for param in decl.params:
                self._collect_type_imports(
                    param.type,
                    ffi_names=ffi_names,
                    mark_opaque=mark_opaque,
                    mark_simd=mark_simd,
                    mark_complex=mark_complex,
                    mark_atomic=mark_atomic,
                )
        elif isinstance(decl, GlobalDecl):
            self._collect_type_imports(
                decl.value_type,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )

    def _collect_const_expr_imports(
        self,
        expr: MojoConstExpr,
        *,
        ffi_names: set[str],
        mark_opaque,
        mark_simd,
        mark_complex,
        mark_atomic,
    ) -> None:
        if isinstance(
            expr,
            (
                MojoIntLiteral,
                MojoFloatLiteral,
                MojoStringLiteral,
                MojoCharLiteral,
                MojoRefExpr,
            ),
        ):
            return
        if isinstance(expr, MojoUnaryExpr):
            self._collect_const_expr_imports(
                expr.operand,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            return
        if isinstance(expr, MojoBinaryExpr):
            self._collect_const_expr_imports(
                expr.lhs,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            self._collect_const_expr_imports(
                expr.rhs,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            return
        if isinstance(expr, MojoCastExpr):
            self._collect_type_imports(
                expr.target,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            self._collect_const_expr_imports(
                expr.expr,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            return
        if isinstance(expr, MojoSizeOfExpr):
            self._collect_type_imports(
                expr.target,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            return

    def _collect_type_imports(
        self,
        t: MojoType,
        *,
        ffi_names: set[str],
        mark_opaque,
        mark_simd,
        mark_complex,
        mark_atomic,
    ) -> None:
        if isinstance(t, BuiltinType):
            if t.name.value.startswith("c_"):
                ffi_names.add(t.name.value)
            return
        if isinstance(t, NamedType):
            return
        if isinstance(t, PointerType):
            if t.pointee is None:
                mark_opaque()
            else:
                self._collect_type_imports(
                    t.pointee,
                    ffi_names=ffi_names,
                    mark_opaque=mark_opaque,
                    mark_simd=mark_simd,
                    mark_complex=mark_complex,
                    mark_atomic=mark_atomic,
                )
            return
        if isinstance(t, ArrayType):
            self._collect_type_imports(
                t.element,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            return
        if isinstance(t, ParametricType):
            if t.base.value == "SIMD":
                mark_simd()
            elif t.base.value == "ComplexSIMD":
                mark_complex()
            elif t.base.value == "Atomic":
                mark_atomic()
            elif t.base.value == "UnsafeUnion":
                ffi_names.add("UnsafeUnion")
            for arg in t.args:
                if isinstance(arg, TypeArg):
                    self._collect_type_imports(
                        arg.type,
                        ffi_names=ffi_names,
                        mark_opaque=mark_opaque,
                        mark_simd=mark_simd,
                        mark_complex=mark_complex,
                        mark_atomic=mark_atomic,
                    )
            return
        if isinstance(t, CallbackType):
            for param in t.params:
                self._collect_type_imports(
                    param.type,
                    ffi_names=ffi_names,
                    mark_opaque=mark_opaque,
                    mark_simd=mark_simd,
                    mark_complex=mark_complex,
                    mark_atomic=mark_atomic,
                )
            self._collect_type_imports(
                t.ret,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            return
        if isinstance(t, FunctionType):
            for param in t.params:
                self._collect_type_imports(
                    param,
                    ffi_names=ffi_names,
                    mark_opaque=mark_opaque,
                    mark_simd=mark_simd,
                    mark_complex=mark_complex,
                    mark_atomic=mark_atomic,
                )
            self._collect_type_imports(
                t.ret,
                ffi_names=ffi_names,
                mark_opaque=mark_opaque,
                mark_simd=mark_simd,
                mark_complex=mark_complex,
                mark_atomic=mark_atomic,
            )
            return
        raise NormalizeMojoModuleError(f"unsupported MojoType node: {type(t).__name__!r}")

    def _set_flag(self, name: str) -> None:
        if name == "opaque":
            self._needs_opaque_imports = True
        elif name == "simd":
            self._needs_simd_import = True
        elif name == "complex":
            self._needs_complex_import = True
        elif name == "atomic":
            self._needs_atomic_import = True

    def _effective_link_mode(self, decl: FunctionDecl) -> LinkMode:
        if (
            decl.call_target.link_mode == LinkMode.EXTERNAL_CALL
            and not decl.call_target.symbol
            and self._module.link_mode != LinkMode.EXTERNAL_CALL
        ):
            return self._module.link_mode
        return decl.call_target.link_mode

    @staticmethod
    def _callback_type_from_type(t: MojoType | None) -> CallbackType | None:
        if t is None:
            return None
        if isinstance(t, CallbackType):
            return t
        if isinstance(t, FunctionType):
            return CallbackType(
                params=[CallbackParam(name="", type=param) for param in t.params],
                ret=t.ret,
            )
        return None


def normalize_mojo_module(module: MojoModule) -> MojoModule:
    """Normalize MojoIR into a form the printer can emit directly."""

    return NormalizeMojoModulePass().run(module)


__all__ = [
    "NormalizeMojoModuleError",
    "NormalizeMojoModulePass",
    "normalize_mojo_module",
]
