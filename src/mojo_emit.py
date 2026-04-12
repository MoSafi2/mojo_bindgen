# src/mojo_emit.py — emit thin Mojo FFI from bindgen Unit IR.
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Literal

from src.ir import (
    Array,
    Bitfield,
    Const,
    Decl,
    Enum,
    Enumerant,
    Field,
    Function,
    FunctionPtr,
    Opaque,
    Param,
    Pointer,
    Primitive,
    PrimitiveKind,
    Struct,
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


def lower_type(t: Type, ctx: _TypeContext, struct_name_for_nested: str | None = None) -> str:
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
    if isinstance(t, Bitfield):
        return lower_primitive(t.backing_type)
    if isinstance(t, Struct):
        if t.is_union:
            # Mojo has no C-compatible union; pass-by-value uses an opaque byte array of the C size.
            ctx.needs_inline_array = True
            return f"InlineArray[UInt8, {t.size_bytes}]"
        name = t.name.strip() if t.name else ""
        if name:
            mid = mojo_ident(name)
            ctx.struct_refs.add(mid)
            return mid
        # Anonymous struct — caller should lift with a synthetic name; use placeholder.
        ctx.struct_refs.add(struct_name_for_nested or "AnonymousStruct")
        return struct_name_for_nested or "AnonymousStruct"
    raise TypeError(f"unsupported type: {type(t)!r}")


def _type_ok_for_register_passable_field(t: Type) -> bool:
    """
    Whether a field type can appear on a struct that conforms to RegisterPassable.
    Conservative: fixed-size arrays (InlineArray in Mojo) are excluded.
    """
    if isinstance(t, (Primitive, Bitfield, Opaque, FunctionPtr)):
        return True
    if isinstance(t, Pointer):
        if t.pointee is None:
            return True
        return _type_ok_for_register_passable_field(t.pointee)
    if isinstance(t, Array):
        return t.size is None and _type_ok_for_register_passable_field(t.element)
    if isinstance(t, Struct):
        if t.is_union:
            return False
        return all(_type_ok_for_register_passable_field(f.type) for f in t.fields)
    return False


def _struct_decl_register_passable(decl: Struct) -> bool:
    if decl.is_union:
        return False
    return all(_type_ok_for_register_passable_field(f.type) for f in decl.fields)


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
        if isinstance(ty, Struct) and ty.name.strip():
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


def _emit_field(
    f: Field,
    index: int,
    *,
    parent_for_anon: str,
    options: MojoEmitOptions,
) -> tuple[str, list[str]]:
    """Return (lines, extra prelude lines for function-pointer comments)."""
    ctx = _new_ctx()
    extra: list[str] = []
    if isinstance(f.type, Struct) and not f.type.name.strip():
        syn = f"{parent_for_anon}_{_field_mojo_name(f, index)}"
        type_str = lower_type(f.type, ctx, struct_name_for_nested=mojo_ident(syn))
    else:
        type_str = lower_type(f.type, ctx, struct_name_for_nested=None)

    fname = _field_mojo_name(f, index)
    lines: list[str] = []

    if isinstance(f.type, Bitfield):
        lines.append(
            f"    # bitfield: C bits {f.type.bit_offset}..{f.type.bit_offset + f.type.bit_width - 1} "
            f"({f.type.bit_width} bits) on {f.type.backing_type.name}"
        )

    if isinstance(f.type, FunctionPtr):
        lines.append(f"    # {_function_ptr_comment(f.type)}")

    if options.warn_abi and isinstance(f.type, Bitfield):
        lines.append("    # ABI: verify bitfield layout matches target C compiler.")

    lines.append(f"    var {fname}: {type_str}")
    return "\n".join(lines), extra


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
        tstr = lower_type(f.type, ctx, struct_name_for_nested=f"{name}_{_field_mojo_name(f, i)}")
        field_label = f.name if f.name else "(anonymous)"
        lines.append(f"#   {field_label}: {tstr}")
    lines.append("")
    return "\n".join(lines)


def _emit_struct(decl: Struct, options: MojoEmitOptions) -> str:
    name = mojo_ident(decl.name.strip() or decl.c_name.strip())
    traits = (
        "(Copyable, Movable, RegisterPassable)"
        if _struct_decl_register_passable(decl)
        else "(Copyable, Movable)"
    )
    lines: list[str] = [f"@fieldwise_init", f"struct {name}{traits}:"]

    if options.warn_abi:
        lines.insert(0, f"# struct {decl.c_name} — size={decl.size_bytes} align={decl.align_bytes} (verify packed/aligned ABI)")

    for i, f in enumerate(decl.fields):
        block, _ = _emit_field(f, i, parent_for_anon=name, options=options)
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


def _emit_function(fn: Function, options: MojoEmitOptions) -> str:
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
        c_sig = f"{ret_t} {fn.link_name}({args_sig}, ...)"
        return f"# variadic C function — not callable from thin FFI:\n# {c_sig}\n"

    # Build call argument list
    call_args = ", ".join(pnames)

    is_void = ret_t == "NoneType"
    ret_list = "NoneType" if is_void else ret_t

    if not fn.is_variadic and isinstance(fn.ret, Struct) and not _struct_decl_register_passable(fn.ret):
        c_sig = f"{ret_t} {fn.link_name}({args_sig})"
        return (
            f"# C return type is not RegisterPassable — external_call cannot model this return; bind manually.\n"
            f"# {c_sig}\n\n"
        )

    if options.linking == "external_call":
        # external_call["sym", Ret, T0, T1](...)
        type_params = [f'"{fn.link_name}"', ret_list]
        for p in params:
            ctxa = _new_ctx()
            type_params.append(lower_type(p.type, ctxa))
        bracket_inner = ", ".join(type_params)
        if is_void:
            body = f"external_call[{bracket_inner}]({call_args})"
            sig = f"def {mojo_ident(fn.name)}({args_sig}) -> None:"
            return f"{sig}\n    {body}\n\n"
        body = f"return external_call[{bracket_inner}]({call_args})"
        sig = f"def {mojo_ident(fn.name)}({args_sig}) -> {ret_t}:"
        return f"{sig}\n    {body}\n\n"

    # owned_dl_handle — use lib.call["sym", Ret, ...](...)
    type_params = [f'"{fn.link_name}"', ret_list]
    for p in params:
        ctxa = _new_ctx()
        type_params.append(lower_type(p.type, ctxa))
    bracket_inner = ", ".join(type_params)
    if is_void:
        body = f"_bindgen_dl().call[{bracket_inner}]({call_args})"
        sig = f"def {mojo_ident(fn.name)}({args_sig}) raises -> None:"
    else:
        body = f"return _bindgen_dl().call[{bracket_inner}]({call_args})"
        sig = f"def {mojo_ident(fn.name)}({args_sig}) raises -> {ret_t}:"
    return f"{sig}\n    {body}\n\n"


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


def _emit_typedef(decl: Typedef, emitted_struct_enum_names: set[str]) -> str:
    if decl.name in emitted_struct_enum_names:
        return ""
    ctx = _new_ctx()
    tstr = lower_type(decl.aliased, ctx)
    return f"comptime {mojo_ident(decl.name)} = {tstr}\n\n"


def _emit_const(decl: Const) -> str:
    t = lower_primitive(decl.type)
    return f"comptime {mojo_ident(decl.name)} = {t}({decl.value})\n\n"


def emit_unit(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Render a Mojo source module as a string."""
    opts = options or MojoEmitOptions()
    chunks: list[str] = []

    if opts.module_comment:
        chunks.append(
            "\n".join(
                [
                    "# Generated by mojo_bindgen — do not edit by hand.",
                    f"# source: {unit.source_header}",
                    f"# library: {unit.library}  link_name: {unit.link_name}",
                    f"# FFI mode: {opts.linking}",
                    "",
                ]
            )
        )

    imports: list[str] = ["from std.ffi import DEFAULT_RTLD, OwnedDLHandle"]
    if opts.linking == "external_call":
        imports = ["from std.ffi import external_call"]
    else:
        imports = ["from std.ffi import DEFAULT_RTLD, OwnedDLHandle"]

    chunks.append("\n".join(imports) + "\n\n")

    if opts.linking == "owned_dl_handle":
        if opts.library_path_hint:
            path_lit = opts.library_path_hint.replace("\\", "\\\\").replace('"', '\\"')
            chunks.append(f'comptime _BINDGEN_LIB_PATH: String = "{path_lit}"\n\n')
            chunks.append(
                "def _bindgen_dl() raises -> OwnedDLHandle:\n"
                "    return OwnedDLHandle(_BINDGEN_LIB_PATH)\n\n"
            )
        else:
            chunks.append(
                "# Resolve symbols from libraries already linked into this process (e.g. mojo link step).\n"
                "def _bindgen_dl() raises -> OwnedDLHandle:\n"
                "    return OwnedDLHandle(DEFAULT_RTLD)\n\n"
            )

    struct_decls = [d for d in unit.decls if isinstance(d, Struct) and not d.is_union]
    sorted_structs = _toposort_structs(struct_decls)

    for d in unit.decls:
        if isinstance(d, Struct) and d.is_union:
            chunks.append(_emit_union_comment(d))

    emitted_names: set[str] = set()
    for s in sorted_structs:
        emitted_names.add(mojo_ident(s.name.strip() or s.c_name.strip()))

    enum_decls = [d for d in unit.decls if isinstance(d, Enum)]
    for e in enum_decls:
        emitted_names.add(mojo_ident(e.name))

    for s in sorted_structs:
        chunks.append(_emit_struct(s, opts))

    for d in unit.decls:
        if isinstance(d, Enum):
            chunks.append(_emit_enum(d))
        elif isinstance(d, Typedef):
            chunks.append(_emit_typedef(d, emitted_names))
        elif isinstance(d, Const):
            chunks.append(_emit_const(d))
        elif isinstance(d, Function):
            chunks.append(_emit_function(d, opts))

    return "".join(chunks)
