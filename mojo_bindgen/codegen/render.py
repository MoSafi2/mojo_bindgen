"""Render analyzed Mojo codegen state to source text."""

from __future__ import annotations

from mojo_bindgen.codegen.mojo_emit_options import MojoEmitOptions
from mojo_bindgen.codegen.mojo_mapper import pointer_origin_names
from mojo_bindgen.ir import Unit
from mojo_bindgen.passes.analyze_for_mojo import (
    AnalyzedBitfieldMember,
    AnalyzedBitfieldStorage,
    AnalyzedCallbackAlias,
    AnalyzedConst,
    AnalyzedEnum,
    AnalyzedFunction,
    AnalyzedGlobalVar,
    AnalyzedMacro,
    AnalyzedStruct,
    AnalyzedStructInitializer,
    AnalyzedStructInitParam,
    AnalyzedTypedef,
    AnalyzedUnion,
    AnalyzedUnit,
    TailDecl,
)


class CodeBuilder:
    """Indented line buffer for Mojo source emission."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._level = 0

    def indent(self) -> None:
        self._level += 1

    def dedent(self) -> None:
        self._level = max(0, self._level - 1)

    def add(self, line: str) -> None:
        self._lines.append("    " * self._level + line)

    def render(self) -> str:
        return "" if not self._lines else "\n".join(self._lines)


def _storage_mask_text(width: int) -> str:
    if width <= 0:
        return "0"
    return hex((1 << width) - 1)


class MojoRenderer:
    """Turn :class:`AnalyzedUnit` into a generated Mojo module."""

    def __init__(self, analyzed: AnalyzedUnit) -> None:
        self._a = analyzed

    @staticmethod
    def _emit_field_lines(b: CodeBuilder, analyzed_field) -> None:
        for line in analyzed_field.comment_lines:
            b.add(line)
        b.add(f"var {analyzed_field.mojo_name}: {analyzed_field.surface_type_text}")

    def _render_opaque_struct_stub(self, analyzed: AnalyzedStruct) -> str:
        b = CodeBuilder()
        b.add(f"# incomplete C struct `{analyzed.decl.c_name}` — opaque; use only as pointer target")
        b.add("@fieldwise_init")
        b.add(f"struct {analyzed.mojo_name}(Copyable, Movable):")
        b.indent()
        b.add("pass")
        b.dedent()
        b.add("")
        return b.render()

    def _render_pure_bitfield_storage(self, b: CodeBuilder, storage: AnalyzedBitfieldStorage) -> None:
        for line in storage.comment_lines:
            b.add(line)
        b.add(f"var {storage.name}: {storage.surface_type_text}")

    def _render_pure_bitfield_member(self, b: CodeBuilder, member: AnalyzedBitfieldMember) -> None:
        surface_type = member.surface_type_text
        storage_type = member.storage_type_text
        mask_text = _storage_mask_text(member.bit_width)
        shift = member.storage_local_bit_offset

        for line in member.comment_lines:
            b.add(line)

        b.add(f"def {member.mojo_name}(self) -> {surface_type}:")
        b.indent()
        b.add(f"var raw = (self.{member.storage_name} >> {shift}) & {storage_type}({mask_text})")
        if member.is_bool:
            b.add(f"return raw != {storage_type}(0)")
        elif member.is_signed and member.bit_width > 0:
            sign_bit_text = hex(1 << (member.bit_width - 1))
            b.add(f"if raw & {storage_type}({sign_bit_text}) != {storage_type}(0):")
            b.indent()
            b.add(f"return {surface_type}(raw | ~{storage_type}({mask_text}))")
            b.dedent()
            b.add(f"return {surface_type}(raw)")
        else:
            b.add(f"return {surface_type}(raw)")
        b.dedent()

        b.add(f"def set_{member.mojo_name}(mut self, value: {surface_type}):")
        b.indent()
        if member.is_bool:
            b.add(f"var raw_value = {storage_type}(1) if value else {storage_type}(0)")
        else:
            b.add(f"var raw_value = {storage_type}(value) & {storage_type}({mask_text})")
        b.add(f"var clear_mask = ~({storage_type}({mask_text}) << {shift})")
        b.add(
            f"self.{member.storage_name} = (self.{member.storage_name} & clear_mask) | "
            f"((raw_value & {storage_type}({mask_text})) << {shift})"
        )
        b.dedent()

    def _render_struct_initializer(
        self,
        b: CodeBuilder,
        analyzed: AnalyzedStruct,
        initializer: AnalyzedStructInitializer,
    ) -> None:
        params = ", ".join(self._render_struct_init_param(param) for param in initializer.params)
        b.add(f"def __init__(out self{', ' if params else ''}{params}):")
        b.indent()
        assert analyzed.bitfield_layout is not None
        for storage in analyzed.bitfield_layout.storages:
            b.add(f"self.{storage.name} = {storage.surface_type_text}(0)")
        for param in initializer.params:
            b.add(f"self.set_{param.name}({param.name})")
        b.dedent()

    @staticmethod
    def _render_struct_init_param(param: AnalyzedStructInitParam) -> str:
        return f"{param.name}: {param.surface_type_text}"

    def _render_struct_body(self, b: CodeBuilder, analyzed: AnalyzedStruct) -> None:
        vars_in_order: list[tuple[int, str, object]] = [(af.index, "field", af) for af in analyzed.fields]
        if analyzed.bitfield_layout is not None:
            vars_in_order.extend(
                (storage.field_index, "storage", storage)
                for storage in analyzed.bitfield_layout.storages
            )
        vars_in_order.sort(key=lambda item: item[0])
        for _, kind, item in vars_in_order:
            if kind == "field":
                self._emit_field_lines(b, item)
            else:
                self._render_pure_bitfield_storage(b, item)
        if analyzed.init_kind == "synthesized":
            for initializer in analyzed.synthesized_initializers:
                self._render_struct_initializer(b, analyzed, initializer)
        if analyzed.bitfield_layout is not None:
            for member in analyzed.bitfield_layout.members:
                self._render_pure_bitfield_member(b, member)

    def render_struct(self, analyzed: AnalyzedStruct) -> str:
        if not analyzed.decl.is_complete:
            return self._render_opaque_struct_stub(analyzed)
        b = CodeBuilder()
        for line in analyzed.header_comment_lines:
            b.add(line)
        for line in analyzed.decorator_lines:
            b.add(line)
        if analyzed.emit_fieldwise_init:
            b.add("@fieldwise_init")
        traits = f"({', '.join(analyzed.trait_names)})" if analyzed.trait_names else ""
        b.add(f"struct {analyzed.mojo_name}{traits}:")
        b.indent()
        self._render_struct_body(b, analyzed)
        b.dedent()
        b.add("")
        return b.render()

    def render(self) -> str:
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
            if isinstance(d, (AnalyzedConst, AnalyzedMacro)):
                chunks.append(self._emit_tail_decl(d))
        chunks.append(self._emit_union_section())
        for s in self._a.ordered_structs:
            chunks.append(self.render_struct(s))
        for d in self._a.tail_decls:
            if isinstance(d, (AnalyzedConst, AnalyzedMacro)):
                continue
            chunks.append(self._emit_tail_decl(d))
        return "".join(chunks)

    def _module_header(self) -> str:
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
        if not self._a.semantic_fallback_notes:
            return ""
        return "\n".join([*(f"# NOTE: {note}" for note in self._a.semantic_fallback_notes), ""])

    def _dl_handle_helpers(self) -> str:
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

    def _emit_callback_alias(self, alias: AnalyzedCallbackAlias) -> str:
        if alias.emit_expr_text is None:
            return "\n".join(alias.comment_lines) + "\n"
        return f"comptime {alias.name} = {alias.emit_expr_text}\n\n"

    def _emit_callback_alias_section(self) -> str:
        return "" if not self._a.callback_aliases else "".join(
            self._emit_callback_alias(alias) for alias in self._a.callback_aliases
        )

    def _emit_union_section(self) -> str:
        chunks: list[str] = []
        for union in self._a.unions:
            chunks.append(f"comptime {union.mojo_name} = {union.comptime_expr_text}\n\n")
            chunks.append("\n".join(union.comment_lines))
        return "".join(chunks)

    def _emit_enum(self, analyzed: AnalyzedEnum) -> str:
        b = CodeBuilder()
        b.add(analyzed.comment_line)
        b.add("@fieldwise_init")
        b.add(f"struct {analyzed.mojo_name}(Copyable, Movable, RegisterPassable):")
        b.indent()
        b.add(f"var value: {analyzed.base_text}")
        for name, value_text in analyzed.enumerants:
            b.add(f"comptime {name} = {value_text}")
        b.dedent()
        b.add("")
        return b.render()

    def _emit_typedef(self, analyzed: AnalyzedTypedef) -> str:
        if analyzed.skip_duplicate or analyzed.callback_alias_name is not None:
            return ""
        return f"comptime {analyzed.mojo_name} = {analyzed.rhs_text}\n\n"

    def _emit_const(self, analyzed: AnalyzedConst) -> str:
        if analyzed.rendered_value_text is None:
            return f"# constant {analyzed.decl.name}: {analyzed.unsupported_reason}\n\n"
        return f"comptime {analyzed.mojo_name} = {analyzed.rendered_value_text}\n\n"

    def _emit_macro(self, analyzed: AnalyzedMacro) -> str:
        if analyzed.rendered_value_text is not None:
            return f"comptime {analyzed.mojo_name} = {analyzed.rendered_value_text}\n\n"
        if analyzed.body_text:
            return f"# macro {analyzed.decl.name}: {analyzed.reason}\n# define {analyzed.decl.name} {analyzed.body_text}\n\n"
        return f"# macro {analyzed.decl.name}: {analyzed.reason}\n# define {analyzed.decl.name}\n\n"

    def _emit_global_var_runtime_structs(self) -> str:
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
        decl = ag.decl
        if ag.kind == "stub":
            const_kw = "const " if decl.is_const else ""
            reason = ag.stub_reason or "manual binding required"
            return f"# global variable {decl.link_name}: {const_kw}{ag.surface_type} ({reason})\n\n"
        link_lit = decl.link_name.replace("\\", "\\\\").replace('"', '\\"')
        wrapper = "GlobalConst" if decl.is_const else "GlobalVar"
        return (
            f"# global `{decl.link_name}` -> {ag.surface_type}\n"
            f'comptime {ag.mojo_name} = {wrapper}[T={ag.surface_type}, link="{link_lit}"]\n\n'
        )

    def _emit_function_variadic(self, analyzed: AnalyzedFunction) -> str:
        return (
            "# variadic C function - not callable from thin FFI:\n"
            f"# {analyzed.rendered_return_type_text} {analyzed.decl.link_name}({analyzed.rendered_args_sig}, ...)\n"
        )

    def _emit_function_non_register_return(self, analyzed: AnalyzedFunction) -> str:
        return (
            "# C return type is not RegisterPassable - external_call cannot model this return; bind manually.\n"
            f"# {analyzed.rendered_return_type_text} {analyzed.decl.link_name}({analyzed.rendered_args_sig})\n\n"
        )

    def _emit_function_thin_wrapper(self, analyzed: AnalyzedFunction) -> str:
        is_void = analyzed.rendered_ret_list_text == "NoneType"
        b = CodeBuilder()
        if self._a.opts.linking == "external_call":
            if is_void:
                b.add(f'def {analyzed.emitted_name}({analyzed.rendered_args_sig}) abi("C") -> None:')
                b.indent()
                b.add(f"external_call[{analyzed.rendered_bracket_inner_text}]({analyzed.rendered_call_args})")
            else:
                b.add(f'def {analyzed.emitted_name}({analyzed.rendered_args_sig}) abi("C") -> {analyzed.rendered_return_type_text}:')
                b.indent()
                b.add(f"return external_call[{analyzed.rendered_bracket_inner_text}]({analyzed.rendered_call_args})")
        else:
            if is_void:
                b.add(f"def {analyzed.emitted_name}({analyzed.rendered_args_sig}) raises -> None:")
                b.indent()
                b.add(f"_bindgen_dl().call[{analyzed.rendered_bracket_inner_text}]({analyzed.rendered_call_args})")
            else:
                b.add(f"def {analyzed.emitted_name}({analyzed.rendered_args_sig}) raises -> {analyzed.rendered_return_type_text}:")
                b.indent()
                b.add(f"return _bindgen_dl().call[{analyzed.rendered_bracket_inner_text}]({analyzed.rendered_call_args})")
        b.dedent()
        b.add("")
        return b.render() + "\n"

    def _emit_function(self, analyzed: AnalyzedFunction) -> str:
        if analyzed.kind == "variadic_stub":
            return self._emit_function_variadic(analyzed)
        if analyzed.kind == "non_register_return_stub":
            return self._emit_function_non_register_return(analyzed)
        return self._emit_function_thin_wrapper(analyzed)

    def _emit_tail_decl(self, decl: TailDecl) -> str:
        if isinstance(decl, AnalyzedEnum):
            return self._emit_enum(decl)
        if isinstance(decl, AnalyzedTypedef):
            return self._emit_typedef(decl)
        if isinstance(decl, AnalyzedConst):
            return self._emit_const(decl)
        if isinstance(decl, AnalyzedMacro):
            return self._emit_macro(decl)
        if isinstance(decl, AnalyzedGlobalVar):
            return self._emit_analyzed_global_var(decl)
        if isinstance(decl, AnalyzedFunction):
            return self._emit_function(decl)
        raise TypeError(f"unexpected tail decl {type(decl)!r}")


def render_struct(analyzed: AnalyzedStruct, options: MojoEmitOptions) -> str:
    dummy = AnalyzedUnit(
        unit=Unit(source_header="", library="", link_name="", decls=[]),
        opts=options,
        needs_opaque_imports=False,
        needs_simd_import=False,
        needs_complex_import=False,
        needs_atomic_import=False,
        needs_global_symbol_helpers=False,
        semantic_fallback_notes=tuple(),
        union_alias_names=frozenset(),
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
