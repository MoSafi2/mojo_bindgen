"""Emit thin Mojo FFI from bindgen Unit IR.

Typedefs whose name matches an already-emitted struct or enum are skipped
(see analysis / :class:`~mojo_bindgen.mojo_analyze.AnalyzedTypedef`) to avoid duplicate
aliases.

Type lowering policy (canonical vs typedef name)
------------------------------------------------
IR may contain :class:`~mojo_bindgen.ir.TypeRef` (C typedef name + canonical
type). Use **canonical** lowering everywhere ABI must match layout and FFI
wire types: struct/union fields, array elements, function-pointer parameter
and return types inside :class:`~mojo_bindgen.ir.FunctionPtr`, and the type
lists passed to ``external_call[...]`` / ``OwnedDLHandle.call[...]``.

Use the **typedef name** (as a Mojo identifier) on **top-level function**
``def`` signatures — parameters and return type — when a matching
``comptime`` typedef alias is emitted in this module, so POSIX-style names
like ``size_t`` survive in the API surface.

Top-level ``typedef`` declarations use ``canonical`` for the RHS so the alias
target is a concrete Mojo type (or transparent chain toward one).

Codegen pipeline
----------------
1. :func:`emit_unit` accepts :class:`~mojo_bindgen.ir.Unit` IR plus optional
   :class:`~mojo_bindgen.mojo_emit_options.MojoEmitOptions`.
2. :func:`~mojo_bindgen.mojo_analyze.analyze_unit` walks the IR and produces an
   :class:`~mojo_bindgen.mojo_analyze.AnalyzedUnit` (sorted structs, union
   blocks, lowered typedefs, thin function wrappers).
3. :class:`MojoModuleEmitter` renders that analysis to a single Mojo source
   string (prelude, imports, helpers, unions, structs, then tail declarations).
"""

from __future__ import annotations

from mojo_bindgen.ir import Const, Enum, Unit
from mojo_bindgen.codegen.lowering import (
    FFIOriginStyle,
    TypeLowerer,
    lower_primitive,
    lower_type,
    mojo_ident,
)
from mojo_bindgen.codegen.mojo_analyze import (
    AnalyzedField,
    AnalyzedFunction,
    AnalyzedStruct,
    AnalyzedTypedef,
    AnalyzedUnit,
    TailDecl,
    analyzed_struct_for_test,
    analyze_unit,
    struct_by_mojo_name,
)
from mojo_bindgen.codegen.mojo_emit_options import LinkingMode, MojoEmitOptions

# Re-exports for callers and tests
__all__ = [
    "AnalyzedFunction",
    "AnalyzedStruct",
    "AnalyzedTypedef",
    "AnalyzedUnit",
    "CodeBuilder",
    "FFIOriginStyle",
    "LinkingMode",
    "MojoEmitOptions",
    "MojoModuleEmitter",
    "TypeLowerer",
    "analyzed_struct_for_test",
    "analyze_unit",
    "emit_struct",
    "emit_unit",
    "lower_type",
    "mojo_ident",
    "struct_by_mojo_name",
]


class CodeBuilder:
    """Indented line buffer for Mojo source emission."""

    def __init__(self) -> None:
        """Start with an empty buffer at indent level zero."""
        self._lines: list[str] = []
        self._level = 0

    def indent(self) -> None:
        """Increase indentation for subsequent ``add`` / ``extend`` lines."""
        self._level += 1

    def dedent(self) -> None:
        """Decrease indentation (floor at zero)."""
        self._level = max(0, self._level - 1)

    def add(self, line: str) -> None:
        """Append one line with the current indent prefix."""
        self._lines.append("    " * self._level + line)

    def extend(self, lines: list[str]) -> None:
        """Append each line in ``lines`` using the current indent level."""
        for ln in lines:
            self.add(ln)

    def render(self) -> str:
        """Join buffered lines with newlines, or empty string if none."""
        if not self._lines:
            return ""
        return "\n".join(self._lines)


class MojoModuleEmitter:
    """Turns :class:`~mojo_bindgen.mojo_analyze.AnalyzedUnit` into Mojo source text.

    Call :meth:`emit` after :func:`~mojo_bindgen.mojo_analyze.analyze_unit` has
    produced ordering, lowered types, and per-declaration emission plans.
    """

    def __init__(self, analyzed: AnalyzedUnit) -> None:
        """Bind the pre-analyzed unit used by :meth:`emit`."""
        self._a = analyzed

    @staticmethod
    def _emit_field_lines(opts: MojoEmitOptions, b: CodeBuilder, af: AnalyzedField) -> None:
        """Emit comments and ``var name: type`` for one struct field (bitfields, fn pointers, ABI hints)."""
        f = af.field
        if f.is_bitfield:
            b.add(
                f"# bitfield: C bits {f.bit_offset}..{f.bit_offset + f.bit_width - 1} "
                f"({f.bit_width} bits) on {f.type.name}"
            )
        if af.fn_ptr_comment is not None:
            b.add(f"# {af.fn_ptr_comment}")
        if opts.warn_abi and f.is_bitfield:
            b.add("# ABI: verify bitfield layout matches target C compiler.")
        b.add(f"var {af.mojo_name}: {af.canonical_type}")

    @staticmethod
    def emit_struct(opts: MojoEmitOptions, analyzed: AnalyzedStruct) -> str:
        """Emit one non-union ``struct`` definition from pre-analyzed data."""
        decl = analyzed.decl
        name = mojo_ident(decl.name.strip() or decl.c_name.strip())
        traits = (
            "(Copyable, Movable, RegisterPassable)"
            if analyzed.register_passable
            else "(Copyable, Movable)"
        )
        b = CodeBuilder()
        if opts.warn_abi:
            b.add(
                f"# struct {decl.c_name} — size={decl.size_bytes} align={decl.align_bytes} "
                "(verify packed/aligned ABI)"
            )
        if opts.emit_align:
            if analyzed.align_decorator is not None:
                b.add(f"@align({analyzed.align_decorator})")
                if analyzed.align_stride_warning:
                    b.add(
                        "# FFI: array stride follows size_of[T](); only T[0] is guaranteed "
                        "align_of[T]-aligned; pad struct size to a multiple of alignment for per-element alignment."
                    )
            elif analyzed.align_omit_comment is not None:
                b.add(analyzed.align_omit_comment)
        b.add("@fieldwise_init")
        b.add(f"struct {name}{traits}:")
        b.indent()
        for af in analyzed.fields:
            MojoModuleEmitter._emit_field_lines(opts, b, af)
        b.dedent()
        b.add("")
        return b.render()

    def emit(self) -> str:
        """Concatenate all sections into one Mojo module (see module *Codegen pipeline*)."""
        chunks: list[str] = []
        if self._a.opts.module_comment:
            chunks.append(self._module_header())
        chunks.append(self._import_block())
        chunks.append(self._dl_handle_helpers())
        chunks.append(self._emit_union_section())
        for s in self._a.sorted_structs:
            chunks.append(MojoModuleEmitter.emit_struct(self._a.opts, s))
        for d in self._a.tail_decls:
            chunks.append(self._emit_tail_decl(d))
        return "".join(chunks)

    def _module_header(self) -> str:
        """Leading generated-file comment (source path, library, link mode)."""
        a = self._a
        return "\n".join(
            [
                "# Generated by mojo_bindgen — do not edit by hand.",
                f"# source: {a.source_header}",
                f"# library: {a.library}  link_name: {a.link_name}",
                f"# FFI mode: {a.opts.linking}",
                "",
            ]
        )

    def _import_block(self) -> str:
        """``std.ffi`` imports (and opaque pointers if needed) for this unit."""
        lines: list[str] = []
        if self._a.opts.linking == "external_call":
            ffi_names = ["external_call"]
            if self._a.unsafe_union_comptime:
                ffi_names.append("UnsafeUnion")
            lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        else:
            ffi_names = ["DEFAULT_RTLD", "OwnedDLHandle"]
            if self._a.unsafe_union_comptime:
                ffi_names.append("UnsafeUnion")
            lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        if self._a.needs_opaque_imports:
            lines.append("from std.memory import ImmutOpaquePointer, MutOpaquePointer")
        return "\n".join(lines) + "\n\n"

    def _dl_handle_helpers(self) -> str:
        """``_bindgen_dl`` helper when using ``owned_dl_handle`` linking; else empty."""
        if self._a.opts.linking != "owned_dl_handle":
            return ""
        if self._a.opts.library_path_hint:
            path_lit = self._a.opts.library_path_hint.replace("\\", "\\\\").replace('"', '\\"')
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

    def _emit_union_section(self) -> str:
        """UnsafeUnion comptime lines plus reference comments for C unions."""
        return "".join(
            (ub.comptime or "") + ub.comment_block for ub in self._a.union_blocks
        )

    def _emit_enum(self, decl: Enum) -> str:
        """Emit a wrapper ``struct`` for a C ``enum`` with comptime enumerants."""
        base = lower_primitive(decl.underlying)
        name = mojo_ident(decl.name)
        u_spelling = decl.underlying.name
        b = CodeBuilder()
        b.add(f"# enum {decl.c_name} — underlying {u_spelling} → {base} (verify C ABI)")
        b.add("@fieldwise_init")
        b.add(f"struct {name}(Copyable, Movable, RegisterPassable):")
        b.indent()
        b.add(f"var value: {base}")
        for e in decl.enumerants:
            b.add(f"comptime {mojo_ident(e.name)} = Self({base}({e.value}))")
        b.dedent()
        b.add("")
        return b.render()

    def _emit_typedef(self, t: AnalyzedTypedef) -> str:
        """Emit ``comptime`` alias for a typedef, or nothing if duplicate of struct/enum."""
        if t.skip_duplicate:
            return ""
        n = mojo_ident(t.decl.name)
        return f"comptime {n} = {t.mojo_type_rhs}\n\n"

    def _emit_const(self, decl: Const) -> str:
        """Emit a ``comptime`` for a C ``#define`` / constant."""
        t = lower_primitive(decl.type)
        return f"comptime {mojo_ident(decl.name)} = {t}({decl.value})\n\n"

    def _emit_function_variadic(self, fn: AnalyzedFunction) -> str:
        """Comment-only stub: variadic C functions are not thin-FFI callable."""
        c_sig = f"{fn.ret_t} {fn.decl.link_name}({fn.args_sig}, ...)"
        return f"# variadic C function — not callable from thin FFI:\n# {c_sig}\n"

    def _emit_function_non_register_return(self, fn: AnalyzedFunction) -> str:
        """Comment-only stub when the C return is not ``RegisterPassable``."""
        c_sig = f"{fn.ret_t} {fn.decl.link_name}({fn.args_sig})"
        return (
            "# C return type is not RegisterPassable — external_call cannot model this return; bind manually.\n"
            f"# {c_sig}\n\n"
        )

    def _emit_function_thin_wrapper(self, fn: AnalyzedFunction) -> str:
        """``external_call`` or ``OwnedDLHandle.call`` wrapper for a normal function."""
        bracket_inner = fn.bracket_inner
        name = mojo_ident(fn.decl.name)
        b = CodeBuilder()
        if self._a.opts.linking == "external_call":
            if fn.is_void:
                b.add(f'def {name}({fn.args_sig}) abi("C") -> None:')
                b.indent()
                b.add(f"external_call[{bracket_inner}]({fn.call_args})")
            else:
                b.add(f'def {name}({fn.args_sig}) abi("C") -> {fn.ret_t}:')
                b.indent()
                b.add(f"return external_call[{bracket_inner}]({fn.call_args})")
        else:
            if fn.is_void:
                b.add(f"def {name}({fn.args_sig}) raises -> None:")
                b.indent()
                b.add(f"_bindgen_dl().call[{bracket_inner}]({fn.call_args})")
            else:
                b.add(f"def {name}({fn.args_sig}) raises -> {fn.ret_t}:")
                b.indent()
                b.add(f"return _bindgen_dl().call[{bracket_inner}]({fn.call_args})")
        b.dedent()
        b.add("")
        return b.render() + "\n"

    def _emit_function(self, fn: AnalyzedFunction) -> str:
        """Dispatch on :attr:`~mojo_bindgen.mojo_analyze.AnalyzedFunction.kind`."""
        if fn.kind == "variadic_stub":
            return self._emit_function_variadic(fn)
        if fn.kind == "non_register_return_stub":
            return self._emit_function_non_register_return(fn)
        return self._emit_function_thin_wrapper(fn)

    def _emit_tail_decl(self, decl: TailDecl) -> str:
        """Emit one enum, typedef alias, const, or function from the tail list."""
        if isinstance(decl, Enum):
            return self._emit_enum(decl)
        if isinstance(decl, AnalyzedTypedef):
            return self._emit_typedef(decl)
        if isinstance(decl, Const):
            return self._emit_const(decl)
        if isinstance(decl, AnalyzedFunction):
            return self._emit_function(decl)
        raise TypeError(f"unexpected tail decl {type(decl)!r}")


emit_struct = MojoModuleEmitter.emit_struct


def emit_unit(unit: Unit, options: MojoEmitOptions | None = None) -> str:
    """Run the codegen pipeline: analyze ``unit``, then emit a Mojo module string.

    Parameters
    ----------
    unit
        Parsed C header IR (:class:`~mojo_bindgen.ir.Unit`).
    options
        FFI linking, ABI comments, and pointer provenance; defaults are used
        when omitted.

    Returns
    -------
    str
        Full ``.mojo`` source for this binding unit.
    """
    opts = options or MojoEmitOptions()
    analyzed = analyze_unit(unit, opts)
    return MojoModuleEmitter(analyzed).emit()
