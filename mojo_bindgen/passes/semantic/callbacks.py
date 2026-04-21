"""Callback alias collection over normalized IR."""

from __future__ import annotations

from dataclasses import dataclass

from mojo_bindgen.codegen.mojo_mapper import mojo_ident, peel_wrappers
from mojo_bindgen.ir import Function, FunctionPtr, GlobalVar, Struct, Type, TypeRef, Typedef, Unit


@dataclass(frozen=True)
class CallbackAlias:
    """Generated callback signature alias for a surfaced function-pointer type."""

    name: str
    fp: FunctionPtr


@dataclass(frozen=True)
class CallbackAliasInfo:
    aliases: tuple[CallbackAlias, ...]
    signature_names: frozenset[str]
    field_aliases: dict[tuple[str, int], str]
    typedef_aliases: dict[str, str]
    fn_param_aliases: dict[tuple[str, int], str]
    fn_ret_aliases: dict[str, str]
    global_aliases: dict[str, str]


def _supports_callback_alias(fp: FunctionPtr) -> bool:
    if fp.is_variadic:
        return False
    if fp.calling_convention is None:
        return True
    return fp.calling_convention.lower() in {"c", "cdecl", "default"}


def _function_ptr_from_type(t: Type) -> FunctionPtr | None:
    core = peel_wrappers(t)
    return core if isinstance(core, FunctionPtr) else None


def _unique_callback_alias(base: str, used: set[str]) -> str:
    candidate = mojo_ident(base)
    if candidate not in used:
        used.add(candidate)
        return candidate
    i = 2
    while True:
        named = f"{candidate}_{i}"
        if named not in used:
            used.add(named)
            return named
        i += 1


def collect_callback_aliases(
    unit: Unit,
    emitted_typedef_names: frozenset[str],
) -> CallbackAliasInfo:
    aliases: list[CallbackAlias] = []
    alias_names: set[str] = set()
    field_aliases: dict[tuple[str, int], str] = {}
    typedef_aliases: dict[str, str] = {}
    fn_param_aliases: dict[tuple[str, int], str] = {}
    fn_ret_aliases: dict[str, str] = {}
    global_aliases: dict[str, str] = {}

    def ensure_alias(fp: FunctionPtr, preferred: str) -> str:
        alias = _unique_callback_alias(preferred, alias_names)
        aliases.append(CallbackAlias(name=alias, fp=fp))
        return alias

    for decl in unit.decls:
        if isinstance(decl, Typedef):
            fp = _function_ptr_from_type(decl.aliased)
            if (
                fp is not None
                and _supports_callback_alias(fp)
                and mojo_ident(decl.name) in emitted_typedef_names
            ):
                typedef_aliases[decl.decl_id] = ensure_alias(fp, decl.name)
        elif isinstance(decl, Struct) and not decl.is_union:
            base = decl.name.strip() or decl.c_name.strip()
            for i, field in enumerate(decl.fields):
                fp = _function_ptr_from_type(field.type)
                if fp is not None and _supports_callback_alias(fp):
                    field_name = field.source_name or field.name or f"field_{i}"
                    suffix = field_name if field_name.endswith("cb") else f"{field_name}_cb"
                    field_aliases[(decl.decl_id, i)] = ensure_alias(fp, f"{base}_{suffix}")
        elif isinstance(decl, Function):
            fp = _function_ptr_from_type(decl.ret)
            if fp is not None and _supports_callback_alias(fp):
                if isinstance(decl.ret, TypeRef) and mojo_ident(decl.ret.name) in emitted_typedef_names:
                    fn_ret_aliases[decl.decl_id] = mojo_ident(decl.ret.name)
                else:
                    fn_ret_aliases[decl.decl_id] = ensure_alias(fp, f"{decl.name}_return_cb")
            for i, param in enumerate(decl.params):
                fp = _function_ptr_from_type(param.type)
                if fp is not None and _supports_callback_alias(fp):
                    if isinstance(param.type, TypeRef) and mojo_ident(param.type.name) in emitted_typedef_names:
                        fn_param_aliases[(decl.decl_id, i)] = mojo_ident(param.type.name)
                    else:
                        pname = param.name or f"arg{i}"
                        fn_param_aliases[(decl.decl_id, i)] = ensure_alias(fp, f"{decl.name}_{pname}_cb")
        elif isinstance(decl, GlobalVar):
            fp = _function_ptr_from_type(decl.type)
            if fp is not None and _supports_callback_alias(fp):
                if isinstance(decl.type, TypeRef) and mojo_ident(decl.type.name) in emitted_typedef_names:
                    global_aliases[decl.decl_id] = mojo_ident(decl.type.name)
                else:
                    global_aliases[decl.decl_id] = ensure_alias(fp, f"{decl.name}_cb")

    return CallbackAliasInfo(
        aliases=tuple(aliases),
        signature_names=frozenset(alias_names),
        field_aliases=field_aliases,
        typedef_aliases=typedef_aliases,
        fn_param_aliases=fn_param_aliases,
        fn_ret_aliases=fn_ret_aliases,
        global_aliases=global_aliases,
    )


class CollectCallbackAliasesPass:
    """Collect callback alias facts for surfaced function-pointer types."""

    def run(
        self,
        unit: Unit,
        *,
        emitted_typedef_names: frozenset[str],
    ) -> CallbackAliasInfo:
        return collect_callback_aliases(unit, emitted_typedef_names)
