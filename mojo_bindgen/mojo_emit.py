# mojo_bindgen/mojo_emit.py — emit thin Mojo FFI from bindgen Unit IR.
#
# Typedefs whose name matches an already-emitted struct or enum are skipped
# (see _emit_typedef / emitted_struct_enum_names) to avoid duplicate aliases.
from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Set
from dataclasses import dataclass
from typing import Literal

from mojo_bindgen.ir import (
    Array,
    Const,
    Enum,
    Field,
    Function,
    FunctionPtr,
    Opaque,
    Param,
    Pointer,
    Primitive,
    PrimitiveKind,
    Struct,
    StructRef,
    Type,
    Typedef,
    Unit,
)

LinkingMode = Literal["external_call", "owned_dl_handle"]

# Mojo keywords and reserved — append underscore if collision.
_MOJO_RESERVED = frozenset(
    """
    def struct fn var let inout mut ref copy owned deinit self Self import from as
    pass return raise raises try except finally with if elif else for while break continue
    and or not is in del alias comptime True False None
    """.split()
)


@dataclass
class MojoEmitOptions:
    """Controls FFI linking and naming of generated output."""

    linking: LinkingMode = "external_call"
    """external_call: link C symbols at mojo build time. owned_dl_handle: resolve via dlopen."""

    library_path_hint: str | None = None
    """If set with owned_dl_handle, pass this path to OwnedDLHandle(...). If None, use DEFAULT_RTLD (symbols must be linked into the process)."""

    module_comment: bool = True
    """Emit a leading comment with source header and library metadata."""

    warn_abi: bool = True
    """Emit comments reminding that packed/aligned layouts need verification."""


def mojo_ident(name: str, *, fallback: str = "field") -> str:
    """Map a C identifier to a safe Mojo name."""
    if not name or not name.strip():
        return fallback
    out = []
    for i, ch in enumerate(name):
        if ch.isalnum() or ch == "_":
            out.append(ch)
        else:
            out.append("_")
    s = "".join(out)
    if s and s[0].isdigit():
        s = "_" + s
    if not s:
        s = fallback
    if s in _MOJO_RESERVED:
        s = s + "_"
    return s


def _int_type_for_size(signed: bool, size_bytes: int) -> str:
    if size_bytes == 1:
        return "Int8" if signed else "UInt8"
    if size_bytes == 2:
        return "Int16" if signed else "UInt16"
    if size_bytes == 4:
        return "Int32" if signed else "UInt32"
    if size_bytes == 8:
        return "Int64" if signed else "UInt64"
    if size_bytes == 16:
        return "Int128" if signed else "UInt128"
    return "Int64"  # fallback


def lower_primitive(p: Primitive) -> str:
    if p.kind == PrimitiveKind.VOID:
        return "NoneType"
    if p.kind == PrimitiveKind.BOOL:
        return "Bool"
    if p.kind == PrimitiveKind.FLOAT:
        if p.size_bytes == 4:
            return "Float32"
        if p.size_bytes == 8:
            return "Float64"
        return "Float64"  # long double / unusual — document via comment at use site
    if p.kind == PrimitiveKind.CHAR:
        # Plain char — treat as Int8 for ABI (signedness varies by platform).
        return "Int8" if p.is_signed else "UInt8"
    if p.kind == PrimitiveKind.INT:
        return _int_type_for_size(p.is_signed, p.size_bytes)
    return "Int32"


class _TypeContext:
    """Tracks struct references while lowering types."""

    def __init__(self) -> None:
        self.struct_refs: set[str] = set()
        self.needs_opaque_pointer = False
        self.needs_unsafe_pointer = False
        self.needs_inline_array = False


def _new_ctx() -> _TypeContext:
    return _TypeContext()


def lower_type(t: Type, ctx: _TypeContext) -> str:
    """Lower IR Type to a Mojo type string."""
    if isinstance(t, Primitive):
        return lower_primitive(t)
    if isinstance(t, Pointer):
        ctx.needs_unsafe_pointer = True
        if t.pointee is None:
            # C void* — opaque address (NoneType pointee + origin for FFI).
            return "UnsafePointer[NoneType, MutAnyOrigin]"
        inner = lower_type(t.pointee, ctx)
        return f"UnsafePointer[{inner}, MutAnyOrigin]"
    if isinstance(t, Array):
        if t.size is None:
            ctx.needs_unsafe_pointer = True
            inner = lower_type(t.element, ctx)
            return f"UnsafePointer[{inner}, MutAnyOrigin]"
        ctx.needs_inline_array = True
        inner = lower_type(t.element, ctx)
        return f"InlineArray[{inner}, {t.size}]"
    if isinstance(t, FunctionPtr):
        ctx.needs_unsafe_pointer = True
        return "UnsafePointer[NoneType, MutAnyOrigin]"
    if isinstance(t, Opaque):
        ctx.needs_unsafe_pointer = True
        return "UnsafePointer[NoneType, MutAnyOrigin]"
    if isinstance(t, StructRef):
        if t.is_union:
            ctx.needs_inline_array = True
            return f"InlineArray[UInt8, {t.size_bytes}]"
        mid = mojo_ident(t.name.strip())
        ctx.struct_refs.add(mid)
        return mid
    raise TypeError(f"unsupported type: {type(t)!r}")


def _struct_by_mojo_name(unit: Unit) -> dict[str, Struct]:
    """Map Mojo struct alias names to struct declarations (non-union only)."""
    out: dict[str, Struct] = {}
    for d in unit.decls:
        if isinstance(d, Struct) and not d.is_union:
            out[mojo_ident(d.name.strip() or d.c_name.strip())] = d
    return out


def _type_ok_for_register_passable_field(t: Type, struct_by_name: dict[str, Struct]) -> bool:
    """
    Whether a field type can appear on a struct that conforms to RegisterPassable.
    Conservative: fixed-size arrays (InlineArray in Mojo) are excluded.
    """
    if isinstance(t, (Primitive, Opaque, FunctionPtr)):
        return True
    if isinstance(t, StructRef):
        mid = mojo_ident(t.name.strip())
        s = struct_by_name.get(mid)
        if s is None or s.is_union:
            return False
        return all(_type_ok_for_register_passable_field(f.type, struct_by_name) for f in s.fields)
    if isinstance(t, Pointer):
        if t.pointee is None:
            return True
        return _type_ok_for_register_passable_field(t.pointee, struct_by_name)
    if isinstance(t, Array):
        return t.size is None and _type_ok_for_register_passable_field(t.element, struct_by_name)
    return False


def _struct_decl_register_passable(decl: Struct, struct_by_name: dict[str, Struct]) -> bool:
    if decl.is_union:
        return False
    return all(_type_ok_for_register_passable_field(f.type, struct_by_name) for f in decl.fields)


def _field_mojo_name(f: Field, index: int) -> str:
    if f.name:
        return mojo_ident(f.name)
    return f"_anon_{index}"


def _function_ptr_comment(fp: FunctionPtr) -> str:
    ctx = _new_ctx()
    parts = [lower_type(fp.ret, ctx)]
    for p in fp.params:
        parts.append(lower_type(p, ctx))
    var = "varargs" if fp.is_variadic else "fixed"
    return f"function pointer ({var}): ({', '.join(parts)})"


def _struct_dependency_edges(s: Struct) -> list[tuple[str, str]]:
    """Return (successor, predecessor) pairs: `succ` depends on `pred` (emit `pred` first)."""
    me = mojo_ident(s.name.strip() or s.c_name.strip())
    edges: list[tuple[str, str]] = []

    def walk(ty: Type) -> None:
        if isinstance(ty, StructRef):
            if ty.is_union:
                return
            pred = mojo_ident(ty.name.strip())
            if pred != me:
                edges.append((me, pred))
            return
        if isinstance(ty, Pointer) and ty.pointee is not None:
            walk(ty.pointee)
        elif isinstance(ty, Array):
            walk(ty.element)
        elif isinstance(ty, FunctionPtr):
            walk(ty.ret)
            for p in ty.params:
                walk(p)

    for f in s.fields:
        walk(f.type)
    return edges


def _toposort_structs(structs: list[Struct]) -> list[Struct]:
    if not structs:
        return []

    def name_of(s: Struct) -> str:
        return mojo_ident(s.name.strip() or s.c_name.strip())

    names = [name_of(s) for s in structs]
    known = set(names)
    name_to_struct = {name_of(s): s for s in structs}

    # graph[pred] = successors that must appear after pred
    graph: dict[str, set[str]] = defaultdict(set)
    indegree: dict[str, int] = {n: 0 for n in names}

    for s in structs:
        succ = name_of(s)
        for succ2, pred in _struct_dependency_edges(s):
            if succ2 != succ:
                continue
            if pred in known and pred != succ:
                if succ not in graph[pred]:
                    graph[pred].add(succ)
                    indegree[succ] += 1

    q = deque(sorted([n for n in names if indegree[n] == 0], key=lambda x: names.index(x)))
    order: list[str] = []
    while q:
        n = q.popleft()
        order.append(n)
        for succ in graph.get(n, ()):
            indegree[succ] -= 1
            if indegree[succ] == 0:
                q.append(succ)

    for n in names:
        if n not in order:
            order.append(n)

    return [name_to_struct[n] for n in order]


@dataclass(frozen=True)
class UnitEmissionPlan:
    """Pure plan for ordering struct and tail declarations."""

    sorted_structs: tuple[Struct, ...]
    emitted_struct_enum_names: frozenset[str]
    tail_decls: tuple[Enum | Typedef | Const | Function, ...]


def _plan_unit_emission(unit: Unit) -> UnitEmissionPlan:
    struct_decls = [d for d in unit.decls if isinstance(d, Struct) and not d.is_union]
    sorted_structs = _toposort_structs(struct_decls)

    emitted_names: set[str] = set()
    for s in sorted_structs:
        emitted_names.add(mojo_ident(s.name.strip() or s.c_name.strip()))

    for d in unit.decls:
        if isinstance(d, Enum):
            emitted_names.add(mojo_ident(d.name))

    tail_decls: list[Enum | Typedef | Const | Function] = []
    for d in unit.decls:
        if isinstance(d, (Enum, Typedef, Const, Function)):
            tail_decls.append(d)

    return UnitEmissionPlan(
        sorted_structs=tuple(sorted_structs),
        emitted_struct_enum_names=frozenset(emitted_names),
        tail_decls=tuple(tail_decls),
    )


def _emit_field(
    f: Field,
    index: int,
    *,
    parent_for_anon: str,
    options: MojoEmitOptions,
) -> str:
    ctx = _new_ctx()
    type_str = lower_type(f.type, ctx)

    fname = _field_mojo_name(f, index)
    lines: list[str] = []

    if f.is_bitfield:
        lines.append(
            f"    # bitfield: C bits {f.bit_offset}..{f.bit_offset + f.bit_width - 1} "
            f"({f.bit_width} bits) on {f.type.name}"
        )

    if isinstance(f.type, FunctionPtr):
        lines.append(f"    # {_function_ptr_comment(f.type)}")

    if options.warn_abi and f.is_bitfield:
        lines.append("    # ABI: verify bitfield layout matches target C compiler.")

    lines.append(f"    var {fname}: {type_str}")
    return "\n".join(lines)


def _emit_union_comment(decl: Struct) -> str:
    """Document a C union; Mojo has no union type — we do not emit a struct."""
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    lines = [
        f"# ── C union `{decl.c_name}` — not emitted (Mojo has no C-compatible union).",
        f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}. By-value uses InlineArray[UInt8, {decl.size_bytes}] in this file.",
        "# Members (reference only):",
    ]
    for i, f in enumerate(decl.fields):
        ctx = _new_ctx()
        tstr = lower_type(f.type, ctx)
        field_label = f.name if f.name else "(anonymous)"
        lines.append(f"#   {field_label}: {tstr}")
    lines.append("")
    return "\n".join(lines)


def _emit_struct(
    decl: Struct, options: MojoEmitOptions, struct_by_name: dict[str, Struct]
) -> str:
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    traits = (
        "(Copyable, Movable, RegisterPassable)"
        if _struct_decl_register_passable(decl, struct_by_name)
        else "(Copyable, Movable)"
    )
    lines: list[str] = [f"@fieldwise_init", f"struct {name}{traits}:"]

    if options.warn_abi:
        lines.insert(0, f"# struct {decl.c_name} — size={decl.size_bytes} align={decl.align_bytes} (verify packed/aligned ABI)")

    for i, f in enumerate(decl.fields):
        block = _emit_field(f, i, parent_for_anon=name, options=options)
        lines.append(block)

    lines.append("")
    return "\n".join(lines)


def _param_names(params: list[Param]) -> list[str]:
    out: list[str] = []
    for i, p in enumerate(params):
        if p.name.strip():
            out.append(mojo_ident(p.name))
        else:
            out.append(f"a{i}")
    return out


def _function_type_param_list(fn: Function, ret_list: str) -> str:
    type_params = [f'"{fn.link_name}"', ret_list]
    for p in fn.params:
        ctxa = _new_ctx()
        type_params.append(lower_type(p.type, ctxa))
    return ", ".join(type_params)


def _emit_function_variadic(fn: Function, ret_t: str, args_sig: str) -> str:
    c_sig = f"{ret_t} {fn.link_name}({args_sig}, ...)"
    return f"# variadic C function — not callable from thin FFI:\n# {c_sig}\n"


def _emit_function_non_register_return(fn: Function, ret_t: str, args_sig: str) -> str:
    c_sig = f"{ret_t} {fn.link_name}({args_sig})"
    return (
        f"# C return type is not RegisterPassable — external_call cannot model this return; bind manually.\n"
        f"# {c_sig}\n\n"
    )


def _emit_function_external_call(
    fn: Function,
    *,
    ret_t: str,
    args_sig: str,
    call_args: str,
    is_void: bool,
    ret_list: str,
) -> str:
    bracket_inner = _function_type_param_list(fn, ret_list)
    if is_void:
        body = f"external_call[{bracket_inner}]({call_args})"
        sig = f"def {mojo_ident(fn.name)}({args_sig}) -> None:"
        return f"{sig}\n    {body}\n\n"
    body = f"return external_call[{bracket_inner}]({call_args})"
    sig = f"def {mojo_ident(fn.name)}({args_sig}) -> {ret_t}:"
    return f"{sig}\n    {body}\n\n"


def _emit_function_owned_dl(
    fn: Function,
    *,
    ret_t: str,
    args_sig: str,
    call_args: str,
    is_void: bool,
    ret_list: str,
) -> str:
    bracket_inner = _function_type_param_list(fn, ret_list)
    if is_void:
        body = f"_bindgen_dl().call[{bracket_inner}]({call_args})"
        sig = f"def {mojo_ident(fn.name)}({args_sig}) raises -> None:"
    else:
        body = f"return _bindgen_dl().call[{bracket_inner}]({call_args})"
        sig = f"def {mojo_ident(fn.name)}({args_sig}) raises -> {ret_t}:"
    return f"{sig}\n    {body}\n\n"


def _emit_function(
    fn: Function, options: MojoEmitOptions, struct_by_name: dict[str, Struct]
) -> str:
    ctx_ret = _new_ctx()
    ret_t = lower_type(fn.ret, ctx_ret)
    params = fn.params
    pnames = _param_names(params)
    arg_decls = []
    for pname, p in zip(pnames, params):
        ctxp = _new_ctx()
        tstr = lower_type(p.type, ctxp)
        arg_decls.append(f"{pname}: {tstr}")

    args_sig = ", ".join(arg_decls)
    if fn.is_variadic:
        return _emit_function_variadic(fn, ret_t, args_sig)

    call_args = ", ".join(pnames)
    is_void = ret_t == "NoneType"
    ret_list = "NoneType" if is_void else ret_t

    if isinstance(fn.ret, StructRef):
        rs = struct_by_name.get(mojo_ident(fn.ret.name.strip()))
        if rs is not None and not _struct_decl_register_passable(rs, struct_by_name):
            return _emit_function_non_register_return(fn, ret_t, args_sig)

    if options.linking == "external_call":
        return _emit_function_external_call(
            fn,
            ret_t=ret_t,
            args_sig=args_sig,
            call_args=call_args,
            is_void=is_void,
            ret_list=ret_list,
        )
    return _emit_function_owned_dl(
        fn,
        ret_t=ret_t,
        args_sig=args_sig,
        call_args=call_args,
        is_void=is_void,
        ret_list=ret_list,
    )


def _emit_enum(decl: Enum) -> str:
    base = lower_primitive(decl.underlying)
    lines = [
        f"comptime {mojo_ident(decl.name)} = {base}",
        "",
    ]
    alias = mojo_ident(decl.name)
    for e in decl.enumerants:
        lines.append(f"comptime {mojo_ident(e.name)} = {alias}({e.value})")
    lines.append("")
    return "\n".join(lines)


def _emit_typedef(decl: Typedef, emitted_struct_enum_names: Set[str]) -> str:
    """Emit ``alias name = …`` unless the typedef name duplicates a struct/enum alias."""
    if decl.name in emitted_struct_enum_names:
        return ""
    ctx = _new_ctx()
    tstr = lower_type(decl.aliased, ctx)
    return f"comptime {mojo_ident(decl.name)} = {tstr}\n\n"


def _emit_const(decl: Const) -> str:
    t = lower_primitive(decl.type)
    return f"comptime {mojo_ident(decl.name)} = {t}({decl.value})\n\n"


class MojoModuleEmitter:
    """Orchestrates prelude, struct ordering, and tail declarations."""

    def __init__(self, options: MojoEmitOptions) -> None:
        self._opts = options

    def emit(self, unit: Unit, plan: UnitEmissionPlan) -> str:
        struct_by_name = _struct_by_mojo_name(unit)
        chunks: list[str] = []
        if self._opts.module_comment:
            chunks.append(self._module_header(unit))
        chunks.append(self._import_block())
        chunks.append(self._dl_handle_helpers())
        chunks.append(self._emit_union_comments(unit))
        for s in plan.sorted_structs:
            chunks.append(_emit_struct(s, self._opts, struct_by_name))
        emitted = plan.emitted_struct_enum_names
        for d in plan.tail_decls:
            chunks.append(self._emit_tail_decl(d, emitted, struct_by_name))
        return "".join(chunks)

    def _module_header(self, unit: Unit) -> str:
        return "\n".join(
            [
                "# Generated by mojo_bindgen — do not edit by hand.",
                f"# source: {unit.source_header}",
                f"# library: {unit.library}  link_name: {unit.link_name}",
                f"# FFI mode: {self._opts.linking}",
                "",
            ]
        )

    def _import_block(self) -> str:
        if self._opts.linking == "external_call":
            imports = ["from std.ffi import external_call"]
        else:
            imports = ["from std.ffi import DEFAULT_RTLD, OwnedDLHandle"]
        return "\n".join(imports) + "\n\n"

    def _dl_handle_helpers(self) -> str:
        if self._opts.linking != "owned_dl_handle":
            return ""
        if self._opts.library_path_hint:
            path_lit = self._opts.library_path_hint.replace("\\", "\\\\").replace('"', '\\"')
            return (
                f'comptime _BINDGEN_LIB_PATH: String = "{path_lit}"\n\n'
                "def _bindgen_dl() raises -> OwnedDLHandle:\n"
                "    return OwnedDLHandle(_BINDGEN_LIB_PATH)\n\n"
            )
        return (
            "# Resolve symbols from libraries already linked into this process (e.g. mojo link step).\n"
            "def _bindgen_dl() raises -> OwnedDLHandle:\n"
            "    return OwnedDLHandle(DEFAULT_RTLD)\n\n"
        )

    def _emit_union_comments(self, unit: Unit) -> str:
        parts: list[str] = []
        for d in unit.decls:
            if isinstance(d, Struct) and d.is_union:
                parts.append(_emit_union_comment(d))
        return "".join(parts)

    def _emit_tail_decl(
        self,
        decl: Enum | Typedef | Const | Function,
        emitted: frozenset[str],
        struct_by_name: dict[str, Struct],
    ) -> str:
        if isinstance(decl, Enum):
            return _emit_enum(decl)
        if isinstance(decl, Typedef):
            return _emit_typedef(decl, emitted)
        if isinstance(decl, Const):
            return _emit_const(decl)
        return _emit_function(decl, self._opts, struct_by_name)


def emit_unit(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Render a Mojo source module as a string."""
    opts = options or MojoEmitOptions()
    plan = _plan_unit_emission(unit)
    return MojoModuleEmitter(opts).emit(unit, plan)
