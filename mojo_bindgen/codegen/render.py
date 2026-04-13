"""Render analyzed Mojo codegen state to source text.

This module is responsible only for formatting. It consumes
:class:`~mojo_bindgen.codegen.analysis.AnalyzedUnit` plus the original IR
declarations referenced from that analysis and emits a single Mojo source file.
"""

from __future__ import annotations

from mojo_bindgen.ir import (
    CharLiteral,
    Const,
    Enum,
    FloatLiteral,
    FunctionPtr,
    GlobalVar,
    IntLiteral,
    NullPtrLiteral,
    Primitive,
    RefExpr,
    StringLiteral,
)
from mojo_bindgen.codegen.analysis import (
    AnalyzedField,
    AnalyzedFunction,
    AnalyzedStruct,
    AnalyzedTypedef,
    AnalyzedUnion,
    AnalyzedUnit,
    TailDecl,
)
from mojo_bindgen.codegen.lowering import TypeLowerer, lower_primitive, mojo_ident
from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions


class CodeBuilder:
    """Indented line buffer for Mojo source emission."""

    def __init__(self) -> None:
        """Initialize an empty builder at indentation level zero."""
        self._lines: list[str] = []
        self._level = 0

    def indent(self) -> None:
        """Increase indentation for subsequently added lines."""
        self._level += 1

    def dedent(self) -> None:
        """Decrease indentation, never dropping below zero."""
        self._level = max(0, self._level - 1)

    def add(self, line: str) -> None:
        """Append one line using the current indentation level."""
        self._lines.append("    " * self._level + line)

    def render(self) -> str:
        """Return the buffered source as a newline-joined string."""
        if not self._lines:
            return ""
        return "\n".join(self._lines)


class MojoRenderer:
    """Turn :class:`AnalyzedUnit` into a generated Mojo module."""

    def __init__(self, analyzed: AnalyzedUnit) -> None:
        """Bind an analyzed unit and prepare the lowerers needed for rendering."""
        self._a = analyzed
        self._types = TypeLowerer(
            ffi_origin=analyzed.opts.ffi_origin,
            unsafe_union_names=analyzed.unsafe_union_names,
            typedef_mojo_names=analyzed.emitted_typedef_mojo_names,
        )
        self._union_member_types = TypeLowerer(
            ffi_origin=analyzed.opts.ffi_origin,
            unsafe_union_names=frozenset(),
            typedef_mojo_names=frozenset(),
        )

    @staticmethod
    def _emit_field_lines(
        opts: MojoEmitOptions,
        types: TypeLowerer,
        b: CodeBuilder,
        analyzed_field: AnalyzedField,
    ) -> None:
        """Emit comments and the field declaration for one analyzed field."""
        field = analyzed_field.field
        if field.is_bitfield:
            b.add(
                f"# bitfield: C bits {field.bit_offset}..{field.bit_offset + field.bit_width - 1} "
                f"({field.bit_width} bits) on {field.type.name}"
            )
        if isinstance(field.type, FunctionPtr):
            b.add(f"# {types.function_ptr_comment(field.type)}")
        if opts.warn_abi and field.is_bitfield:
            b.add("# ABI: verify bitfield layout matches target C compiler.")
        b.add(f"var {analyzed_field.mojo_name}: {types.canonical(field.type)}")

    def render_struct(self, analyzed: AnalyzedStruct) -> str:
        """Render a single analyzed non-union struct declaration."""
        decl = analyzed.decl
        name = mojo_ident(decl.name.strip() or decl.c_name.strip())
        traits = (
            "(Copyable, Movable, RegisterPassable)"
            if analyzed.register_passable
            else "(Copyable, Movable)"
        )
        b = CodeBuilder()
        if self._a.opts.warn_abi:
            b.add(
                f"# struct {decl.c_name} - size={decl.size_bytes} align={decl.align_bytes} "
                "(verify packed/aligned ABI)"
            )
        if self._a.opts.emit_align:
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
            self._emit_field_lines(self._a.opts, self._types, b, af)
        b.dedent()
        b.add("")
        return b.render()

    def render(self) -> str:
        """Render the full analyzed unit to one Mojo module string."""
        chunks: list[str] = []
        if self._a.opts.module_comment:
            chunks.append(self._module_header())
        chunks.append(self._import_block())
        chunks.append(self._dl_handle_helpers())
        chunks.append(self._emit_union_section())
        for s in self._a.ordered_structs:
            chunks.append(self.render_struct(s))
        for d in self._a.tail_decls:
            chunks.append(self._emit_tail_decl(d))
        return "".join(chunks)

    def _module_header(self) -> str:
        """Render the generated-file header comment block."""
        unit = self._a.unit
        return "\n".join(
            [
                "# Generated by mojo_bindgen - do not edit by hand.",
                f"# source: {unit.source_header}",
                f"# library: {unit.library}  link_name: {unit.link_name}",
                f"# FFI mode: {self._a.opts.linking}",
                "",
            ]
        )

    def _import_block(self) -> str:
        """Render the import section required by the analyzed unit."""
        lines: list[str] = []
        if self._a.opts.linking == "external_call":
            ffi_names = ["external_call"]
        else:
            ffi_names = ["DEFAULT_RTLD", "OwnedDLHandle"]
        if self._a.unions and self._a.unsafe_union_names:
            ffi_names.append("UnsafeUnion")
        lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        if self._a.needs_opaque_imports:
            lines.append("from std.memory import ImmutOpaquePointer, MutOpaquePointer")
        return "\n".join(lines) + "\n\n"

    def _dl_handle_helpers(self) -> str:
        """Render helper code for ``owned_dl_handle`` linking mode, if needed."""
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

    def _emit_unsafe_union_comptime_line(self, union: AnalyzedUnion) -> str | None:
        """Render the ``UnsafeUnion`` alias line for an eligible union."""
        if not union.uses_unsafe_union:
            return None
        name = mojo_ident(union.decl.name.strip() or union.decl.c_name.strip())
        types_csv = ", ".join(self._union_member_types.canonical(f.type) for f in union.decl.fields)
        return f"comptime {name}_Union = UnsafeUnion[{types_csv}]\n\n"

    def _union_comment_block(self, union: AnalyzedUnion) -> str:
        """Render the reference comment block describing a C union."""
        decl = union.decl
        name = mojo_ident(decl.name.strip() or decl.c_name.strip())
        if union.uses_unsafe_union:
            lines = [
                f"# -- C union `{decl.c_name}` - comptime `{name}_Union` = UnsafeUnion[...] (trivial members; see std.ffi).",
                f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
                "# Members (reference only):",
            ]
        else:
            lines = [
                f"# -- C union `{decl.c_name}` - not emitted as a struct.",
                f"# By-value uses InlineArray[UInt8, {decl.size_bytes}] unless you wrap a manual UnsafeUnion (unique trivial members).",
                f"# C size={decl.size_bytes} bytes, align={decl.align_bytes}.",
                "# Members (reference only):",
            ]
        for field in decl.fields:
            label = field.name if field.name else "(anonymous)"
            lines.append(f"#   {label}: {self._union_member_types.canonical(field.type)}")
        lines.append("")
        return "\n".join(lines)

    def _emit_union_section(self) -> str:
        """Render all union aliases and reference comments for the module."""
        chunks: list[str] = []
        for union in self._a.unions:
            comptime = self._emit_unsafe_union_comptime_line(union)
            if comptime is not None:
                chunks.append(comptime)
            chunks.append(self._union_comment_block(union))
        return "".join(chunks)

    def _emit_enum(self, decl: Enum) -> str:
        """Render one C enum as a thin Mojo wrapper struct."""
        base = lower_primitive(decl.underlying)
        name = mojo_ident(decl.name)
        b = CodeBuilder()
        b.add(f"# enum {decl.c_name} - underlying {decl.underlying.name} -> {base} (verify C ABI)")
        b.add("@fieldwise_init")
        b.add(f"struct {name}(Copyable, Movable, RegisterPassable):")
        b.indent()
        b.add(f"var value: {base}")
        for e in decl.enumerants:
            b.add(f"comptime {mojo_ident(e.name)} = Self({base}({e.value}))")
        b.dedent()
        b.add("")
        return b.render()

    @staticmethod
    def _emit_typedef(analyzed: AnalyzedTypedef, types: TypeLowerer) -> str:
        """Render one typedef alias unless it is suppressed by analysis."""
        if analyzed.skip_duplicate:
            return ""
        name = mojo_ident(analyzed.decl.name)
        rhs = types.canonical(analyzed.decl.canonical)
        return f"comptime {name} = {rhs}\n\n"

    @staticmethod
    def _emit_const(decl: Const) -> str:
        """Render one constant declaration from the supported ``ConstExpr`` subset.

        Unsupported or pointer-like constant forms are emitted as comments so
        the generated module stays honest about what still requires manual work.
        """
        expr = decl.expr
        name = mojo_ident(decl.name)
        if isinstance(expr, IntLiteral) and isinstance(decl.type, Primitive):
            t = lower_primitive(decl.type)
            return f"comptime {name} = {t}({expr.value})\n\n"
        if isinstance(expr, StringLiteral):
            value = expr.value.replace("\\", "\\\\").replace('"', '\\"')
            return f'comptime {name} = "{value}"\n\n'
        if isinstance(expr, CharLiteral):
            value = expr.value.replace("\\", "\\\\").replace("'", "\\'")
            return f"comptime {name} = '{value}'\n\n"
        if isinstance(expr, FloatLiteral):
            return f"comptime {name} = {expr.value}\n\n"
        if isinstance(expr, RefExpr):
            return f"comptime {name} = {mojo_ident(expr.name)}\n\n"
        if isinstance(expr, NullPtrLiteral):
            return f"# constant {decl.name}: null pointer macro is not emitted directly\n\n"
        return f"# constant {decl.name}: unsupported constant expression form\n\n"

    def _emit_global_var(self, decl: GlobalVar) -> str:
        """Render a reference stub for a top-level global variable.

        Global variables remain part of the IR surface even though thin Mojo
        bindings do not yet generate direct accessors for them.
        """
        ty = self._types.signature(decl.type)
        const_kw = "const " if decl.is_const else ""
        return f"# global variable {decl.link_name}: {const_kw}{ty} (manual binding required)\n\n"

    def _function_signature(self, analyzed: AnalyzedFunction) -> tuple[str, str, str, bool, str]:
        """Build derived signature fragments used by function rendering."""
        fn = analyzed.decl
        ret_t = self._types.signature(fn.ret)
        args_sig = ", ".join(
            f"{name}: {self._types.signature(param.type)}"
            for name, param in zip(analyzed.param_names, fn.params)
        )
        call_args = ", ".join(analyzed.param_names)
        ret_abi = self._types.canonical(fn.ret)
        is_void = ret_abi == "NoneType"
        ret_list = "NoneType" if is_void else ret_abi
        return ret_t, args_sig, call_args, is_void, ret_list

    def _emit_function_variadic(self, analyzed: AnalyzedFunction) -> str:
        """Render the comment stub used for unsupported variadic functions."""
        ret_t, args_sig, _, _, _ = self._function_signature(analyzed)
        return (
            "# variadic C function - not callable from thin FFI:\n"
            f"# {ret_t} {analyzed.decl.link_name}({args_sig}, ...)\n"
        )

    def _emit_function_non_register_return(self, analyzed: AnalyzedFunction) -> str:
        """Render the comment stub for functions with unsupported by-value returns."""
        ret_t, args_sig, _, _, _ = self._function_signature(analyzed)
        return (
            "# C return type is not RegisterPassable - external_call cannot model this return; bind manually.\n"
            f"# {ret_t} {analyzed.decl.link_name}({args_sig})\n\n"
        )

    def _emit_function_thin_wrapper(self, analyzed: AnalyzedFunction) -> str:
        """Render a callable thin-FFI wrapper for one supported function."""
        fn = analyzed.decl
        ret_t, args_sig, call_args, is_void, ret_list = self._function_signature(analyzed)
        bracket_inner = self._types.function_type_param_list(fn, ret_list)
        name = mojo_ident(fn.name)
        b = CodeBuilder()
        if self._a.opts.linking == "external_call":
            if is_void:
                b.add(f'def {name}({args_sig}) abi("C") -> None:')
                b.indent()
                b.add(f"external_call[{bracket_inner}]({call_args})")
            else:
                b.add(f'def {name}({args_sig}) abi("C") -> {ret_t}:')
                b.indent()
                b.add(f"return external_call[{bracket_inner}]({call_args})")
        else:
            if is_void:
                b.add(f"def {name}({args_sig}) raises -> None:")
                b.indent()
                b.add(f"_bindgen_dl().call[{bracket_inner}]({call_args})")
            else:
                b.add(f"def {name}({args_sig}) raises -> {ret_t}:")
                b.indent()
                b.add(f"return _bindgen_dl().call[{bracket_inner}]({call_args})")
        b.dedent()
        b.add("")
        return b.render() + "\n"

    def _emit_function(self, analyzed: AnalyzedFunction) -> str:
        """Dispatch to the appropriate function rendering strategy."""
        if analyzed.kind == "variadic_stub":
            return self._emit_function_variadic(analyzed)
        if analyzed.kind == "non_register_return_stub":
            return self._emit_function_non_register_return(analyzed)
        return self._emit_function_thin_wrapper(analyzed)

    def _emit_tail_decl(self, decl: TailDecl) -> str:
        """Render one non-struct declaration from the analyzed unit tail."""
        if isinstance(decl, Enum):
            return self._emit_enum(decl)
        if isinstance(decl, AnalyzedTypedef):
            return self._emit_typedef(decl, self._types)
        if isinstance(decl, Const):
            return self._emit_const(decl)
        if isinstance(decl, GlobalVar):
            return self._emit_global_var(decl)
        if isinstance(decl, AnalyzedFunction):
            return self._emit_function(decl)
        raise TypeError(f"unexpected tail decl {type(decl)!r}")


def render_struct(analyzed: AnalyzedStruct, options: MojoEmitOptions) -> str:
    """Render a single analyzed struct outside full-unit rendering.

    This helper is primarily used by focused unit tests that want the struct
    renderer without constructing a complete analyzed module.
    """
    from mojo_bindgen.ir import Unit

    dummy = AnalyzedUnit(
        unit=Unit(source_header="", library="", link_name="", decls=[]),
        opts=options,
        needs_opaque_imports=False,
        unsafe_union_names=frozenset(),
        emitted_typedef_mojo_names=frozenset(),
        ordered_structs=(analyzed,),
        unions=tuple(),
        tail_decls=tuple(),
    )
    return MojoRenderer(dummy).render_struct(analyzed)
