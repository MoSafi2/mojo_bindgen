"""Tail-declaration Mojo analysis."""

from __future__ import annotations

from mojo_bindgen.analysis.callbacks import CallbackAliasInfo
from mojo_bindgen.analysis.common import mojo_float_literal_text, scalar_comment_name
from mojo_bindgen.analysis.layout import LayoutFacts
from mojo_bindgen.analysis.model import (
    AnalyzedCallbackAlias,
    AnalyzedConst,
    AnalyzedEnum,
    AnalyzedFunction,
    AnalyzedGlobalVar,
    AnalyzedMacro,
    AnalyzedTypedef,
    TailDecl,
)
from mojo_bindgen.analysis.names import EmissionNameFacts
from mojo_bindgen.codegen.mojo_mapper import TypeMapper, mojo_ident, peel_wrappers
from mojo_bindgen.ir import (
    AtomicType,
    BinaryExpr,
    CastExpr,
    CharLiteral,
    Const,
    Enum,
    FloatLiteral,
    FloatType,
    Function,
    GlobalVar,
    IntLiteral,
    IntType,
    MacroDecl,
    NullPtrLiteral,
    QualifiedType,
    RefExpr,
    StringLiteral,
    Struct,
    StructRef,
    Typedef,
    TypeRef,
    UnaryExpr,
    Unit,
    UnsupportedType,
    VoidType,
)


class AnalyzeTailDeclPass:
    """Analyze non-struct declaration lowering into render-ready facts."""

    def run(
        self,
        unit: Unit,
        *,
        name_facts: EmissionNameFacts,
        callback_info: CallbackAliasInfo,
        layout_facts: LayoutFacts,
        type_mapper: TypeMapper,
    ) -> tuple[tuple[TailDecl, ...], tuple[AnalyzedCallbackAlias, ...]]:
        callback_aliases = tuple(
            self._analyze_callback_alias(alias, type_mapper) for alias in callback_info.aliases
        )
        tail_decls: list[TailDecl] = []
        for decl in unit.decls:
            if isinstance(decl, Typedef):
                tail_decls.append(
                    AnalyzedTypedef(
                        decl=decl,
                        skip_duplicate=mojo_ident(decl.name) in name_facts.emitted_names,
                        mojo_name=mojo_ident(decl.name),
                        rhs_text=type_mapper.surface(decl.aliased),
                        callback_alias_name=callback_info.typedef_aliases.get(decl.decl_id),
                    )
                )
            elif isinstance(decl, Function):
                tail_decls.append(
                    self._analyze_function(
                        decl,
                        layout_facts.struct_map,
                        layout_facts.register_passable_by_decl_id,
                        callback_info,
                        type_mapper,
                    )
                )
            elif isinstance(decl, GlobalVar):
                tail_decls.append(self._analyze_global_var(decl, callback_info, type_mapper))
            elif isinstance(decl, Enum):
                tail_decls.append(self._analyze_enum(decl, type_mapper))
            elif isinstance(decl, Const):
                tail_decls.append(self._analyze_const(decl, type_mapper))
            elif isinstance(decl, MacroDecl):
                tail_decls.append(self._analyze_macro(decl, type_mapper))
        return tuple(tail_decls), callback_aliases

    def _analyze_callback_alias(self, alias, type_mapper: TypeMapper) -> AnalyzedCallbackAlias:
        expr = type_mapper.callback_signature_alias_expr(alias.fp)
        if expr is None:
            return AnalyzedCallbackAlias(
                name=alias.name,
                emit_expr_text=None,
                comment_lines=(
                    f"# callback alias {alias.name}: unsupported callback signature shape",
                    f"# {type_mapper.function_ptr_comment(alias.fp)}",
                    "",
                ),
            )
        return AnalyzedCallbackAlias(name=alias.name, emit_expr_text=expr)

    def _analyze_global_var(
        self,
        decl: GlobalVar,
        callback_info: CallbackAliasInfo,
        type_mapper: TypeMapper,
    ) -> AnalyzedGlobalVar:
        callback_alias = callback_info.global_aliases.get(decl.decl_id)
        surface_type = (
            type_mapper.callback_pointer_type(callback_alias)
            if callback_alias is not None
            else type_mapper.surface(decl.type)
        )
        reason = self._global_var_stub_reason(decl)
        return AnalyzedGlobalVar(
            decl=decl,
            kind="stub" if reason is not None else "wrapper",
            surface_type=surface_type,
            mojo_name=mojo_ident(decl.name),
            stub_reason=reason,
        )

    def _global_var_stub_reason(self, decl: GlobalVar) -> str | None:
        t = decl.type
        while True:
            if isinstance(t, AtomicType):
                return "atomic global requires manual binding (use Atomic APIs on a pointer)"
            if isinstance(t, TypeRef):
                t = t.canonical
                continue
            if isinstance(t, QualifiedType):
                t = t.unqualified
                continue
            break
        core = peel_wrappers(decl.type)
        if isinstance(core, UnsupportedType) and (core.size_bytes is None or core.size_bytes == 0):
            return "unsupported global type layout"
        return None

    def _analyze_function(
        self,
        fn: Function,
        struct_map: dict[str, Struct],
        register_passable_by_decl_id: dict[str, bool],
        callback_info: CallbackAliasInfo,
        type_mapper: TypeMapper,
    ) -> AnalyzedFunction:
        param_names = tuple(type_mapper.param_names(fn.params))
        ret_callback_alias_name = callback_info.fn_ret_aliases.get(fn.decl_id)
        param_callback_alias_names = tuple(
            callback_info.fn_param_aliases.get((fn.decl_id, i)) for i in range(len(fn.params))
        )
        kind = "wrapper"
        if fn.is_variadic:
            kind = "variadic_stub"
        else:
            ret_unwrapped = peel_wrappers(fn.ret)
            if isinstance(ret_unwrapped, StructRef):
                struct_decl = struct_map.get(ret_unwrapped.decl_id)
                if struct_decl is not None and not register_passable_by_decl_id.get(
                    struct_decl.decl_id, False
                ):
                    kind = "non_register_return_stub"
        rendered_return_type_text = (
            type_mapper.callback_pointer_type(ret_callback_alias_name)
            if ret_callback_alias_name is not None
            else type_mapper.signature(fn.ret)
        )
        args_sig = ", ".join(
            f"{name}: {type_mapper.callback_pointer_type(alias) if alias is not None else type_mapper.signature(param.type)}"
            for name, param, alias in zip(
                param_names, fn.params, param_callback_alias_names, strict=True
            )
        )
        call_args = ", ".join(param_names)
        ret_abi = type_mapper.canonical(fn.ret)
        is_void = ret_abi == "NoneType"
        ret_list = "NoneType" if is_void else ret_abi
        bracket_inner = type_mapper.function_type_param_list(
            fn,
            ret_list,
            ret_callback_alias_name=ret_callback_alias_name,
            param_callback_alias_names=param_callback_alias_names,
        )
        return AnalyzedFunction(
            decl=fn,
            kind=kind,
            emitted_name=mojo_ident(fn.name),
            param_names=param_names,
            ret_callback_alias_name=ret_callback_alias_name,
            param_callback_alias_names=param_callback_alias_names,
            rendered_return_type_text=rendered_return_type_text,
            rendered_args_sig=args_sig,
            rendered_call_args=call_args,
            rendered_ret_list_text=ret_list,
            rendered_bracket_inner_text=bracket_inner,
        )

    def _analyze_enum(self, decl: Enum, type_mapper: TypeMapper) -> AnalyzedEnum:
        base = type_mapper.emit_scalar(decl.underlying)
        return AnalyzedEnum(
            decl=decl,
            mojo_name=mojo_ident(decl.name),
            base_text=base,
            comment_line=f"# enum {decl.c_name} - underlying {scalar_comment_name(decl.underlying)} -> {base} (verify C ABI)",
            enumerants=tuple(
                (mojo_ident(enumerant.name), f"Self({base}({enumerant.value}))")
                for enumerant in decl.enumerants
            ),
        )

    def _analyze_const(self, decl: Const, type_mapper: TypeMapper) -> AnalyzedConst:
        rendered = self._render_const_expr(decl.expr, decl.type, type_mapper)
        reason = None
        if rendered is None:
            if isinstance(decl.expr, NullPtrLiteral):
                reason = "null pointer macro is not emitted directly"
            else:
                reason = "unsupported constant expression form"
        return AnalyzedConst(
            decl=decl,
            mojo_name=mojo_ident(decl.name),
            rendered_value_text=rendered,
            unsupported_reason=reason,
        )

    def _analyze_macro(self, decl: MacroDecl, type_mapper: TypeMapper) -> AnalyzedMacro:
        body = " ".join(decl.tokens)
        rendered = None
        reason = decl.diagnostic or decl.kind.replace("_", " ")
        if decl.kind == "object_like_supported" and decl.expr is not None and decl.type is not None:
            if isinstance(decl.expr, RefExpr):
                reason = "identifier reference macro is not emitted directly; only literal macros are currently supported"
            else:
                rendered = self._render_const_expr(decl.expr, decl.type, type_mapper)
                if rendered is None:
                    reason = (
                        "null pointer macro is not emitted directly"
                        if isinstance(decl.expr, NullPtrLiteral)
                        else "parsed macro expression is not emitted directly"
                    )
        return AnalyzedMacro(
            decl=decl,
            mojo_name=mojo_ident(decl.name),
            rendered_value_text=rendered,
            reason=reason,
            body_text=body,
        )

    def _render_const_expr(
        self,
        expr: object,
        decl_type: IntType | FloatType | VoidType | object,
        type_mapper: TypeMapper,
    ) -> str | None:
        if isinstance(expr, IntLiteral) and isinstance(decl_type, (IntType, FloatType, VoidType)):
            return f"{type_mapper.emit_scalar(decl_type)}({expr.value})"
        if isinstance(expr, StringLiteral):
            value = expr.value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{value}"'
        if isinstance(expr, CharLiteral):
            value = expr.value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{value}'"
        if isinstance(expr, FloatLiteral):
            return mojo_float_literal_text(expr.value)
        if isinstance(expr, RefExpr):
            return mojo_ident(expr.name)
        if isinstance(expr, UnaryExpr):
            operand = self._render_const_expr(expr.operand, decl_type, type_mapper)
            return None if operand is None else f"{expr.op}({operand})"
        if isinstance(expr, CastExpr):
            target = expr.target
            if not isinstance(target, IntType):
                return None
            target_text = type_mapper.emit_scalar(target)
            if isinstance(expr.expr, IntLiteral):
                return f"{target_text}({expr.expr.value})"
            inner = self._render_const_expr(expr.expr, target, type_mapper)
            return None if inner is None else f"{target_text}({inner})"
        if isinstance(expr, BinaryExpr):
            lhs = self._render_const_expr(expr.lhs, decl_type, type_mapper)
            rhs = self._render_const_expr(expr.rhs, decl_type, type_mapper)
            return None if lhs is None or rhs is None else f"({lhs} {expr.op} {rhs})"
        if isinstance(expr, NullPtrLiteral):
            return None
        return None


__all__ = ["AnalyzeTailDeclPass"]
