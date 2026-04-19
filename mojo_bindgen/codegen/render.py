"""Render analyzed Mojo codegen state to source text.

This module is responsible only for formatting. It consumes
:class:`~mojo_bindgen.passes.analyze_for_mojo.AnalyzedUnit` plus the original IR
declarations referenced from that analysis and emits a single Mojo source file.
"""

from __future__ import annotations

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import (
    TypeMapper,
    mojo_ident,
    pointer_origin_names,
)
from mojo_bindgen.ir import (
    BinaryExpr,
    CharLiteral,
    Const,
    Enum,
    FloatLiteral,
    FloatType,
    FunctionPtr,
    IntLiteral,
    IntType,
    MacroDecl,
    NullPtrLiteral,
    RefExpr,
    StringLiteral,
    UnaryExpr,
    VoidType,
)
from mojo_bindgen.passes.analyze_for_mojo import (
    AnalyzedField,
    AnalyzedFunction,
    AnalyzedGlobalVar,
    AnalyzedStruct,
    AnalyzedTypedef,
    AnalyzedUnion,
    AnalyzedUnit,
    CallbackAlias,
    TailDecl,
)


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


def _scalar_comment_name(t: IntType | FloatType | VoidType) -> str:
    """Return a compact scalar label for human-facing comments."""
    if isinstance(t, IntType):
        return t.int_kind.value
    if isinstance(t, FloatType):
        return t.float_kind.value
    return "VOID"


def _mojo_float_literal_text(c_spelling: str) -> str:
    """Strip C float suffixes; Mojo has no ``f``/``F``/``l``/``L`` floating literals."""
    t = c_spelling.rstrip()
    while t and t[-1] in "fFlL":
        t = t[:-1]
    return t


class MojoRenderer:
    """Turn :class:`AnalyzedUnit` into a generated Mojo module."""

    def __init__(self, analyzed: AnalyzedUnit) -> None:
        """Bind an analyzed unit and prepare the mappers needed for rendering."""
        self._a = analyzed
        self._types = TypeMapper(
            ffi_origin=analyzed.opts.ffi_origin,
            unsafe_union_names=analyzed.unsafe_union_names,
            typedef_mojo_names=analyzed.emitted_typedef_mojo_names,
            callback_signature_names=analyzed.callback_signature_names,
            ffi_scalar_style=analyzed.opts.ffi_scalar_style,
        )
        self._union_member_types = TypeMapper(
            ffi_origin=analyzed.opts.ffi_origin,
            unsafe_union_names=frozenset(),
            typedef_mojo_names=frozenset(),
            callback_signature_names=frozenset(),
            ffi_scalar_style=analyzed.opts.ffi_scalar_style,
        )

    @staticmethod
    def _emit_field_lines(
        opts: MojoEmitOptions,
        types: TypeMapper,
        b: CodeBuilder,
        analyzed_field: AnalyzedField,
    ) -> None:
        """Emit comments and the field declaration for one analyzed field."""
        field = analyzed_field.field
        if field.is_bitfield:
            backing = (
                _scalar_comment_name(field.type)
                if isinstance(field.type, (IntType, FloatType, VoidType))
                else type(field.type).__name__
            )
            b.add(
                f"# bitfield: C bits {field.bit_offset}..{field.bit_offset + field.bit_width - 1} "
                f"({field.bit_width} bits) on {backing}"
            )
        if analyzed_field.callback_alias_name is None and isinstance(field.type, FunctionPtr):
            b.add(f"# {types.function_ptr_comment(field.type)}")
        if opts.warn_abi and field.is_bitfield:
            b.add("# ABI: verify bitfield layout matches target C compiler.")
        if analyzed_field.callback_alias_name is not None:
            mapped = types.callback_pointer_type(analyzed_field.callback_alias_name)
        else:
            mapped = types.surface(field.type)
        b.add(f"var {analyzed_field.mojo_name}: {mapped}")

    def _render_opaque_struct_stub(self, analyzed: AnalyzedStruct) -> str:
        """Emit a nominal struct for a C incomplete/opaque record (pointer targets only)."""
        decl = analyzed.decl
        name = mojo_ident(decl.name.strip() or decl.c_name.strip())
        b = CodeBuilder()
        b.add(f"# incomplete C struct `{decl.c_name}` — opaque; use only as pointer target")
        b.add("@fieldwise_init")
        b.add(f"struct {name}(Copyable, Movable):")
        b.indent()
        b.add("pass")
        b.dedent()
        b.add("")
        return b.render()

    def render_struct(self, analyzed: AnalyzedStruct) -> str:
        """Render a single analyzed non-union struct declaration."""
        decl = analyzed.decl
        if not decl.is_complete:
            return self._render_opaque_struct_stub(analyzed)
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
        chunks.append(self._semantic_fallback_note_block())
        chunks.append(self._import_block())
        chunks.append(self._dl_handle_helpers())
        if self._a.needs_global_symbol_helpers:
            chunks.append(self._emit_global_var_runtime_structs())
        for s in self._a.ordered_incomplete_structs:
            chunks.append(self.render_struct(s))
        chunks.append(self._emit_callback_alias_section())
        for d in self._a.tail_decls:
            if isinstance(d, (Const, MacroDecl)):
                chunks.append(self._emit_tail_decl(d))
        chunks.append(self._emit_union_section())
        for s in self._a.ordered_structs:
            chunks.append(self.render_struct(s))
        for d in self._a.tail_decls:
            if isinstance(d, (Const, MacroDecl)):
                continue
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
            if self._a.needs_global_symbol_helpers:
                ffi_names.extend(["OwnedDLHandle", "DEFAULT_RTLD"])
        else:
            ffi_names = ["DEFAULT_RTLD", "OwnedDLHandle"]
        if self._a.unions and self._a.unsafe_union_names:
            ffi_names.append("UnsafeUnion")
        scalar = sorted(self._a.ffi_scalar_import_names)
        if scalar:
            ffi_names.extend(scalar)
        lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        if self._a.needs_opaque_imports:
            lines.append("from std.memory import ImmutOpaquePointer, MutOpaquePointer")
        if self._a.needs_simd_import:
            lines.append("from std.builtin.simd import SIMD")
        if self._a.needs_complex_import:
            lines.append("from std.complex import ComplexSIMD")
        if self._a.needs_atomic_import:
            lines.append("from std.atomic import Atomic")
        return "\n".join(lines) + "\n\n"

    def _semantic_fallback_note_block(self) -> str:
        """Render module-level notes for semantic type fallbacks."""
        if not self._a.semantic_fallback_notes:
            return ""
        lines = [f"# NOTE: {note}" for note in self._a.semantic_fallback_notes]
        lines.append("")
        return "\n".join(lines)

    def _dl_handle_helpers(self) -> str:
        """Render helper code for ``owned_dl_handle`` linking mode, if needed."""
        if self._a.opts.linking == "external_call" and self._a.needs_global_symbol_helpers:
            return (
                "# Resolve symbols from libraries already linked into this process (e.g. mojo link step).\n"
                "def _bindgen_dl() raises -> OwnedDLHandle:\n"
                "    return OwnedDLHandle(DEFAULT_RTLD)\n\n"
            )
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
        base = self._types.emit_scalar(decl.underlying)
        name = mojo_ident(decl.name)
        b = CodeBuilder()
        b.add(
            f"# enum {decl.c_name} - underlying {_scalar_comment_name(decl.underlying)} -> {base} (verify C ABI)"
        )
        b.add("@fieldwise_init")
        b.add(f"struct {name}(Copyable, Movable, RegisterPassable):")
        b.indent()
        b.add(f"var value: {base}")
        for e in decl.enumerants:
            b.add(f"comptime {mojo_ident(e.name)} = Self({base}({e.value}))")
        b.dedent()
        b.add("")
        return b.render()

    def _emit_callback_alias(self, alias: CallbackAlias) -> str:
        """Render one surfaced function-pointer callback signature alias."""
        expr = self._types.callback_signature_alias_expr(alias.fp)
        if expr is None:
            return (
                f"# callback alias {alias.name}: unsupported callback signature shape\n"
                f"# {self._types.function_ptr_comment(alias.fp)}\n\n"
            )
        return f"comptime {alias.name} = {expr}\n\n"

    def _emit_callback_alias_section(self) -> str:
        """Render collected callback aliases before the declaration body."""
        if not self._a.callback_aliases:
            return ""
        return "".join(self._emit_callback_alias(alias) for alias in self._a.callback_aliases)

    @staticmethod
    def _emit_typedef(analyzed: AnalyzedTypedef, types: TypeMapper) -> str:
        """Render one typedef alias unless it is suppressed by analysis."""
        if analyzed.skip_duplicate:
            return ""
        if analyzed.callback_alias_name is not None:
            return ""
        name = mojo_ident(analyzed.decl.name)
        rhs = types.surface(analyzed.decl.aliased)
        return f"comptime {name} = {rhs}\n\n"

    def _emit_const(self, decl: Const) -> str:
        """Render one constant declaration from the supported ``ConstExpr`` subset.

        Unsupported or pointer-like constant forms are emitted as comments so
        the generated module stays honest about what still requires manual work.
        """
        expr = decl.expr
        name = mojo_ident(decl.name)
        rendered = self._render_const_expr(expr, decl.type)
        if rendered is None:
            if isinstance(expr, NullPtrLiteral):
                return f"# constant {decl.name}: null pointer macro is not emitted directly\n\n"
            return f"# constant {decl.name}: unsupported constant expression form\n\n"
        return f"comptime {name} = {rendered}\n\n"

    def _emit_macro(self, decl: MacroDecl) -> str:
        """Render one preserved macro declaration.

        Supported object-like macros emit as ``comptime`` constants. All other
        macro forms remain visible as comments with their original token text.
        """
        body = " ".join(decl.tokens)
        if decl.kind == "object_like_supported" and decl.expr is not None and decl.type is not None:
            if isinstance(decl.expr, RefExpr):
                reason = "identifier reference macro is not emitted directly; only literal macros are currently supported"
                if body:
                    return f"# macro {decl.name}: {reason}\n# define {decl.name} {body}\n\n"
                return f"# macro {decl.name}: {reason}\n# define {decl.name}\n\n"
            rendered = self._render_const_expr(decl.expr, decl.type)
            if rendered is not None:
                return f"comptime {mojo_ident(decl.name)} = {rendered}\n\n"
            if isinstance(decl.expr, NullPtrLiteral):
                reason = "null pointer macro is not emitted directly"
            else:
                reason = "parsed macro expression is not emitted directly"
        else:
            reason = decl.diagnostic or decl.kind.replace("_", " ")

        if body:
            return f"# macro {decl.name}: {reason}\n# define {decl.name} {body}\n\n"
        return f"# macro {decl.name}: {reason}\n# define {decl.name}\n\n"

    def _render_const_expr(
        self, expr: object, decl_type: IntType | FloatType | VoidType | object
    ) -> str | None:
        """Render the supported constant-expression subset to Mojo source."""
        if isinstance(expr, IntLiteral) and isinstance(decl_type, (IntType, FloatType, VoidType)):
            t = self._types.emit_scalar(decl_type)
            return f"{t}({expr.value})"
        if isinstance(expr, StringLiteral):
            value = expr.value.replace("\\", "\\\\").replace('"', '\\"')
            return f'"{value}"'
        if isinstance(expr, CharLiteral):
            value = expr.value.replace("\\", "\\\\").replace("'", "\\'")
            return f"'{value}'"
        if isinstance(expr, FloatLiteral):
            return _mojo_float_literal_text(expr.value)
        if isinstance(expr, RefExpr):
            return mojo_ident(expr.name)
        if isinstance(expr, UnaryExpr):
            operand = self._render_const_expr(expr.operand, decl_type)
            if operand is None:
                return None
            return f"{expr.op}({operand})"
        if isinstance(expr, BinaryExpr):
            lhs = self._render_const_expr(expr.lhs, decl_type)
            rhs = self._render_const_expr(expr.rhs, decl_type)
            if lhs is None or rhs is None:
                return None
            return f"({lhs} {expr.op} {rhs})"
        if isinstance(expr, NullPtrLiteral):
            return None
        return None

    def _emit_global_var_runtime_structs(self) -> str:
        """Emit ``GlobalVar`` / ``GlobalConst`` helpers and shared symbol lookup."""
        o = pointer_origin_names(self._a.opts.ffi_origin)
        mut_o = o.mut
        immut_o = o.immut
        return (
            "struct GlobalVar[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:\n"
            "    @staticmethod\n"
            "    def _raw() raises -> UnsafePointer[Self.T, MutAnyOrigin]:\n"
            "        var opt: Optional[UnsafePointer[Self.T, MutAnyOrigin]] = _bindgen_dl().get_symbol[Self.T](StringSlice(Self.link))\n"
            "        if not opt:\n"
            '            raise Error(String("bindgen: missing C global symbol"))\n'
            "        return opt.value()\n"
            "\n"
            "    @staticmethod\n"
            f"    def ptr() raises -> UnsafePointer[Self.T, {mut_o}]:\n"
            f"        return rebind[UnsafePointer[Self.T, {mut_o}]](Self._raw())\n"
            "\n"
            "    @staticmethod\n"
            "    def load() raises -> Self.T:\n"
            "        return Self._raw()[].copy()\n"
            "\n"
            "    @staticmethod\n"
            "    def store(value: Self.T) raises -> None:\n"
            f"        var p = rebind[UnsafePointer[Self.T, {mut_o}]](Self._raw())\n"
            "        p[] = value.copy()\n"
            "\n"
            "\n"
            "struct GlobalConst[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:\n"
            "    @staticmethod\n"
            "    def _raw() raises -> UnsafePointer[Self.T, MutAnyOrigin]:\n"
            "        var opt: Optional[UnsafePointer[Self.T, MutAnyOrigin]] = _bindgen_dl().get_symbol[Self.T](StringSlice(Self.link))\n"
            "        if not opt:\n"
            '            raise Error(String("bindgen: missing C global symbol"))\n'
            "        return opt.value()\n"
            "\n"
            "    @staticmethod\n"
            f"    def ptr() raises -> UnsafePointer[Self.T, {immut_o}]:\n"
            f"        return rebind[UnsafePointer[Self.T, {immut_o}]](Self._raw())\n"
            "\n"
            "    @staticmethod\n"
            "    def load() raises -> Self.T:\n"
            "        return Self._raw()[].copy()\n"
            "\n"
            "\n"
        )

    def _emit_analyzed_global_var(self, ag: AnalyzedGlobalVar) -> str:
        """Render a ``GlobalVar`` / ``GlobalConst`` binding or a manual stub comment."""
        decl = ag.decl
        if ag.kind == "stub":
            const_kw = "const " if decl.is_const else ""
            reason = ag.stub_reason or "manual binding required"
            return f"# global variable {decl.link_name}: {const_kw}{ag.surface_type} ({reason})\n\n"
        link_lit = decl.link_name.replace("\\", "\\\\").replace('"', '\\"')
        wrapper = "GlobalConst" if decl.is_const else "GlobalVar"
        name = mojo_ident(decl.name)
        return (
            f"# global `{decl.link_name}` -> {ag.surface_type}\n"
            f'comptime {name} = {wrapper}[T={ag.surface_type}, link="{link_lit}"]\n\n'
        )

    def _function_signature(self, analyzed: AnalyzedFunction) -> tuple[str, str, str, bool, str]:
        """Build derived signature fragments used by function rendering."""
        fn = analyzed.decl
        ret_t = (
            self._types.callback_pointer_type(analyzed.ret_callback_alias_name)
            if analyzed.ret_callback_alias_name is not None
            else self._types.signature(fn.ret)
        )
        args_sig = ", ".join(
            f"{name}: {self._types.callback_pointer_type(alias) if alias is not None else self._types.signature(param.type)}"
            for name, param, alias in zip(
                analyzed.param_names, fn.params, analyzed.param_callback_alias_names
            )
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
        bracket_inner = self._types.function_type_param_list(
            fn,
            ret_list,
            ret_callback_alias_name=analyzed.ret_callback_alias_name,
            param_callback_alias_names=analyzed.param_callback_alias_names,
        )
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
        if isinstance(decl, MacroDecl):
            return self._emit_macro(decl)
        if isinstance(decl, AnalyzedGlobalVar):
            return self._emit_analyzed_global_var(decl)
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
        needs_simd_import=False,
        needs_complex_import=False,
        needs_atomic_import=False,
        needs_global_symbol_helpers=False,
        semantic_fallback_notes=tuple(),
        unsafe_union_names=frozenset(),
        emitted_typedef_mojo_names=frozenset(),
        callback_aliases=tuple(),
        callback_signature_names=frozenset(),
        global_callback_aliases={},
        ordered_incomplete_structs=tuple(),
        ordered_structs=(analyzed,),
        unions=tuple(),
        tail_decls=tuple(),
        ffi_scalar_import_names=frozenset(),
    )
    return MojoRenderer(dummy).render_struct(analyzed)
