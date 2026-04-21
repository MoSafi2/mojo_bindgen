"""Pretty-print the standalone MojoIR model to Mojo source."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from mojo_bindgen.analysis.common import _mojo_align_decorator_ok, mojo_float_literal_text
from mojo_bindgen.codegen.mojo_mapper import FFIOriginStyle, mojo_ident, pointer_origin_names
from mojo_bindgen.ir import (
    BinaryExpr,
    CastExpr,
    CharLiteral,
    ConstExpr,
    FloatLiteral,
    FloatType,
    IntLiteral,
    IntType,
    NullPtrLiteral,
    RefExpr,
    SizeOfExpr,
    StringLiteral,
    UnaryExpr,
    VoidType,
)
from mojo_bindgen.mojo_ir import (
    PRIMITIVE_BUILTINS,
    AliasDecl,
    AliasKind,
    ArrayType,
    BitfieldGroupMember,
    BuiltinType,
    CallTarget,
    FunctionDecl,
    FunctionKind,
    FunctionType,
    GlobalDecl,
    GlobalKind,
    Initializer,
    LinkMode,
    LoweringNote,
    MojoBuiltin,
    MojoDecl,
    MojoModule,
    MojoType,
    NamedType,
    OpaqueStorageMember,
    PaddingMember,
    ParametricType,
    PointerMutability,
    PointerType,
    StoredMember,
    StructDecl,
    StructKind,
    StructMember,
)


@dataclass(frozen=True)
class MojoIRPrintOptions:
    """Rendering-only policy for standalone MojoIR pretty-printing."""

    ffi_origin: FFIOriginStyle = "external"
    module_comment: bool = True


class MojoIRPrintError(ValueError):
    """Raised when one MojoIR node cannot be rendered as valid Mojo source."""


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

    def extend(self, lines: Iterable[str]) -> None:
        for line in lines:
            self.add(line)

    def render(self) -> str:
        return "" if not self._lines else "\n".join(self._lines)


@dataclass
class _SynthCallbackAlias:
    path: tuple[str, ...]
    name: str
    fn_type: FunctionType


@dataclass
class _ImportState:
    ffi_names: set[str] = field(default_factory=set)
    needs_opaque_imports: bool = False
    needs_simd_import: bool = False
    needs_complex_import: bool = False
    needs_atomic_import: bool = False
    needs_dl_handle_helpers: bool = False
    needs_global_helpers: bool = False


class MojoIRPrinter:
    """Render a standalone :class:`~mojo_bindgen.mojo_ir.MojoModule` to source text."""

    def __init__(self, options: MojoIRPrintOptions | None = None) -> None:
        self._options = options or MojoIRPrintOptions()
        self._origin = pointer_origin_names(self._options.ffi_origin)

    @property
    def options(self) -> MojoIRPrintOptions:
        return self._options

    def render(self, module: MojoModule) -> str:
        self._module = module
        self._imports = _ImportState()
        self._reserved_names = {decl.name for decl in module.decls}
        self._synth_aliases: list[_SynthCallbackAlias] = []
        self._synth_aliases_by_path: dict[tuple[str, ...], _SynthCallbackAlias] = {}
        self._collect_render_requirements(module)
        self._prepass_callback_aliases(module)

        synth_alias_chunks = [
            self._render_synth_callback_alias(alias) for alias in self._synth_aliases
        ]
        decl_chunks = [self._render_decl(decl) for decl in module.decls]

        parts: list[str] = []
        if self._options.module_comment:
            parts.append(self._render_module_header())
        import_block = self._render_import_block()
        if import_block:
            parts.append(import_block)
        helper_block = self._render_helper_blocks()
        if helper_block:
            parts.append(helper_block)
        if synth_alias_chunks:
            parts.append("".join(synth_alias_chunks))
        parts.extend(chunk for chunk in decl_chunks if chunk)
        return "".join(parts)

    def _collect_render_requirements(self, module: MojoModule) -> None:
        if module.capabilities.needs_dl_handle_helpers:
            self._imports.needs_dl_handle_helpers = True
        if module.capabilities.needs_global_helpers:
            self._imports.needs_global_helpers = True
            self._imports.needs_dl_handle_helpers = True
        if module.capabilities.needs_unsafe_union:
            self._imports.ffi_names.add("UnsafeUnion")
        if module.capabilities.needs_simd:
            self._imports.needs_simd_import = True
        if module.capabilities.needs_complex:
            self._imports.needs_complex_import = True
        if module.capabilities.needs_atomic:
            self._imports.needs_atomic_import = True
        if module.capabilities.needs_opaque_pointer_types:
            self._imports.needs_opaque_imports = True

        for decl in module.decls:
            if isinstance(decl, FunctionDecl):
                link_mode = self._function_link_mode(decl)
                if decl.kind == FunctionKind.WRAPPER:
                    if link_mode == LinkMode.EXTERNAL_CALL:
                        self._imports.ffi_names.add("external_call")
                    else:
                        self._imports.needs_dl_handle_helpers = True
                self._walk_decl_types(decl)
            elif isinstance(decl, GlobalDecl):
                if decl.kind == GlobalKind.WRAPPER:
                    self._imports.needs_global_helpers = True
                    self._imports.needs_dl_handle_helpers = True
                self._walk_decl_types(decl)
            else:
                self._walk_decl_types(decl)

    def _walk_decl_types(self, decl: MojoDecl) -> None:
        if isinstance(decl, StructDecl):
            if decl.underlying_type is not None:
                self._walk_type(decl.underlying_type, ())
            for member in decl.members:
                self._walk_member_type(member, ())
            for initializer in decl.initializers:
                for param in initializer.params:
                    self._walk_type(param.type, ())
        elif isinstance(decl, AliasDecl) and decl.type_value is not None:
            self._walk_type(decl.type_value, ())
        elif isinstance(decl, FunctionDecl):
            self._walk_type(decl.return_type, ())
            for param in decl.params:
                self._walk_type(param.type, ())
        elif isinstance(decl, GlobalDecl):
            self._walk_type(decl.value_type, ())

    def _walk_member_type(self, member: StructMember, context: tuple[str, ...]) -> None:
        if isinstance(member, StoredMember):
            self._walk_type(member.type, context)
        elif isinstance(member, BitfieldGroupMember):
            self._walk_type(member.storage_type, context)
            for field in member.fields:
                self._walk_type(field.logical_type, context)

    def _walk_type(self, t: MojoType, context: tuple[str, ...]) -> None:
        if isinstance(t, BuiltinType):
            if t.name.value.startswith("c_"):
                self._imports.ffi_names.add(t.name.value)
            return
        if isinstance(t, NamedType):
            return
        if isinstance(t, PointerType):
            if t.pointee is None:
                self._imports.needs_opaque_imports = True
                return
            self._walk_type(t.pointee, (*context, "pointee"))
            return
        if isinstance(t, ArrayType):
            self._walk_type(t.element, (*context, "element"))
            return
        if isinstance(t, ParametricType):
            if t.base == "SIMD":
                self._imports.needs_simd_import = True
            elif t.base == "ComplexSIMD":
                self._imports.needs_complex_import = True
            elif t.base == "Atomic":
                self._imports.needs_atomic_import = True
            elif t.base == "UnsafeUnion":
                self._imports.ffi_names.add("UnsafeUnion")
            for arg in t.args:
                if arg.startswith("c_"):
                    self._imports.ffi_names.add(arg)
            return
        if isinstance(t, FunctionType):
            self._walk_type(t.ret, (*context, "return"))
            for i, param in enumerate(t.params):
                self._walk_type(param, (*context, f"arg{i}"))
            return
        raise MojoIRPrintError(f"unsupported MojoType node: {type(t).__name__!r}")

    def _prepass_callback_aliases(self, module: MojoModule) -> None:
        for decl in module.decls:
            if isinstance(decl, StructDecl):
                if decl.kind == StructKind.ENUM and decl.underlying_type is not None:
                    self._prepass_type(decl.underlying_type, (decl.name, "underlying"))
                for member in decl.members:
                    if isinstance(member, StoredMember):
                        self._prepass_type(member.type, (decl.name, member.name or "field"))
                    elif isinstance(member, BitfieldGroupMember):
                        self._prepass_type(
                            member.storage_type,
                            (decl.name, member.storage_name or "bitfield_storage"),
                        )
                        for field in member.fields:
                            self._prepass_type(
                                field.logical_type,
                                (decl.name, field.name or "bitfield"),
                            )
                for initializer in decl.initializers:
                    for i, param in enumerate(initializer.params):
                        self._prepass_type(
                            param.type,
                            (decl.name, param.name or f"init_{i}"),
                        )
            elif isinstance(decl, AliasDecl):
                if decl.kind == AliasKind.CALLBACK_SIGNATURE:
                    fn_type = self._callback_signature_type_for_decl(decl)
                    if fn_type is not None:
                        self._prepass_function_signature(fn_type, (decl.name,))
                elif decl.type_value is not None:
                    self._prepass_type(decl.type_value, (decl.name,))
            elif isinstance(decl, FunctionDecl):
                self._prepass_type(decl.return_type, (decl.name, "return"))
                for i, param in enumerate(decl.params):
                    self._prepass_type(
                        param.type,
                        (decl.name, param.name or f"param{i}"),
                    )
            elif isinstance(decl, GlobalDecl):
                self._prepass_type(decl.value_type, (decl.name, "value"))

    def _prepass_type(self, t: MojoType, context: tuple[str, ...]) -> None:
        if isinstance(t, PointerType) and isinstance(t.pointee, FunctionType):
            self._prepass_function_signature(t.pointee, (*context, "signature"))
            self._ensure_callback_alias((*context, "callback"), t.pointee)
            return
        if isinstance(t, PointerType) and t.pointee is not None:
            self._prepass_type(t.pointee, (*context, "pointee"))
            return
        if isinstance(t, ArrayType):
            self._prepass_type(t.element, (*context, "element"))
            return
        if isinstance(t, FunctionType):
            self._prepass_function_signature(t, context)

    def _prepass_function_signature(self, fn_type: FunctionType, context: tuple[str, ...]) -> None:
        self._prepass_type(fn_type.ret, (*context, "return"))
        for i, param in enumerate(fn_type.params):
            self._prepass_type(param, (*context, f"arg{i}"))

    def _ensure_callback_alias(
        self,
        path: tuple[str, ...],
        fn_type: FunctionType,
    ) -> _SynthCallbackAlias:
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

        alias = _SynthCallbackAlias(path=path, name=name, fn_type=fn_type)
        self._synth_aliases_by_path[path] = alias
        self._synth_aliases.append(alias)
        return alias

    def _render_module_header(self) -> str:
        return "\n".join(
            [
                "# Generated from standalone MojoIR.",
                f"# source: {self._module.source_header}",
                f"# library: {self._module.library}  link_name: {self._module.link_name}",
                f"# default link mode: {self._module.link_mode.value}",
                "",
            ]
        )

    def _render_import_block(self) -> str:
        lines: list[str] = []
        ffi_names: list[str] = []
        if "external_call" in self._imports.ffi_names:
            ffi_names.append("external_call")
        if self._imports.needs_dl_handle_helpers:
            ffi_names.extend(["DEFAULT_RTLD", "OwnedDLHandle"])
        if "UnsafeUnion" in self._imports.ffi_names:
            ffi_names.append("UnsafeUnion")
        scalar_imports = sorted(name for name in self._imports.ffi_names if name.startswith("c_"))
        ffi_names.extend(name for name in scalar_imports if name not in ffi_names)
        if ffi_names:
            lines.append(f"from std.ffi import {', '.join(ffi_names)}")
        if self._imports.needs_opaque_imports:
            lines.append("from std.memory import ImmutOpaquePointer, MutOpaquePointer")
        if self._imports.needs_simd_import:
            lines.append("from std.builtin.simd import SIMD")
        if self._imports.needs_complex_import:
            lines.append("from std.complex import ComplexSIMD")
        if self._imports.needs_atomic_import:
            lines.append("from std.atomic import Atomic")
        return "" if not lines else "\n".join(lines) + "\n\n"

    def _render_helper_blocks(self) -> str:
        chunks: list[str] = []
        if self._imports.needs_dl_handle_helpers:
            chunks.append(
                "# Resolve symbols from libraries already linked into this process.\n"
                "def _bindgen_dl() raises -> OwnedDLHandle:\n"
                "    return OwnedDLHandle(DEFAULT_RTLD)\n\n"
            )
        if self._imports.needs_global_helpers:
            chunks.append(
                "struct GlobalVar[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:\n"
                "    @staticmethod\n"
                "    def _raw() raises -> UnsafePointer[Self.T, MutAnyOrigin]:\n"
                "        var opt: Optional[UnsafePointer[Self.T, MutAnyOrigin]] = _bindgen_dl().get_symbol[Self.T](StringSlice(Self.link))\n"
                "        if not opt:\n"
                '            raise Error(String("bindgen: missing C global symbol"))\n'
                "        return opt.value()\n"
                "\n"
                "    @staticmethod\n"
                f"    def ptr() raises -> UnsafePointer[Self.T, {self._origin.mut}]:\n"
                f"        return rebind[UnsafePointer[Self.T, {self._origin.mut}]](Self._raw())\n"
                "\n"
                "    @staticmethod\n"
                "    def load() raises -> Self.T:\n"
                "        return Self._raw()[].copy()\n"
                "\n"
                "    @staticmethod\n"
                "    def store(value: Self.T) raises -> None:\n"
                f"        var p = rebind[UnsafePointer[Self.T, {self._origin.mut}]](Self._raw())\n"
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
                f"    def ptr() raises -> UnsafePointer[Self.T, {self._origin.immut}]:\n"
                f"        return rebind[UnsafePointer[Self.T, {self._origin.immut}]](Self._raw())\n"
                "\n"
                "    @staticmethod\n"
                "    def load() raises -> Self.T:\n"
                "        return Self._raw()[].copy()\n"
                "\n"
                "\n"
            )
        return "".join(chunks)

    def _render_synth_callback_alias(self, alias: _SynthCallbackAlias) -> str:
        expr = self._render_function_signature(alias.fn_type, alias.path)
        return f"comptime {alias.name} = {expr}\n\n"

    def _render_decl(self, decl: MojoDecl) -> str:
        if isinstance(decl, StructDecl):
            return self._render_struct_decl(decl)
        if isinstance(decl, AliasDecl):
            return self._render_alias_decl(decl)
        if isinstance(decl, FunctionDecl):
            return self._render_function_decl(decl)
        if isinstance(decl, GlobalDecl):
            return self._render_global_decl(decl)
        raise MojoIRPrintError(f"unsupported MojoDecl node: {type(decl).__name__!r}")

    def _render_struct_decl(self, decl: StructDecl) -> str:
        b = CodeBuilder()
        b.extend(self._diagnostic_lines(decl.diagnostics))
        if decl.align is not None:
            if _mojo_align_decorator_ok(decl.align):
                b.add(f"@align({decl.align})")
            else:
                b.add(f"# @align omitted: {decl.align} is not a valid Mojo @align value")
        if decl.fieldwise_init:
            b.add("@fieldwise_init")

        traits = list(decl.traits)
        if decl.kind == StructKind.OPAQUE and not traits:
            traits = ["Copyable", "Movable"]
        trait_text = f"({', '.join(traits)})" if traits else ""
        b.add(f"struct {decl.name}{trait_text}:")
        b.indent()
        if decl.kind == StructKind.OPAQUE:
            b.add("pass")
        elif decl.kind == StructKind.ENUM:
            if decl.underlying_type is None:
                raise MojoIRPrintError(f"enum struct {decl.name!r} is missing underlying_type")
            base_text = self._render_type(decl.underlying_type, (decl.name, "underlying"))
            b.add(f"var value: {base_text}")
            for member in decl.enum_members:
                b.add(f"comptime {member.name} = Self({base_text}({member.value}))")
        else:
            self._render_plain_struct_body(b, decl)
        b.dedent()
        b.add("")
        return b.render()

    def _render_plain_struct_body(self, b: CodeBuilder, decl: StructDecl) -> None:
        if not decl.members and not decl.initializers:
            b.add("pass")
            return

        bitfield_names = {
            field.name
            for member in decl.members
            if isinstance(member, BitfieldGroupMember)
            for field in member.fields
        }
        bitfield_storage_types = {
            member.storage_name: self._render_type(
                member.storage_type,
                (decl.name, member.storage_name),
            )
            for member in decl.members
            if isinstance(member, BitfieldGroupMember)
        }

        for member in decl.members:
            if isinstance(member, StoredMember):
                b.add(
                    f"var {member.name}: {self._render_type(member.type, (decl.name, member.name or 'field'))}"
                )
            elif isinstance(member, PaddingMember):
                b.add(f"var {member.name}: InlineArray[UInt8, {member.size_bytes}]")
            elif isinstance(member, OpaqueStorageMember):
                b.add(f"var {member.name}: InlineArray[UInt8, {member.size_bytes}]")
            elif isinstance(member, BitfieldGroupMember):
                b.add(
                    f"var {member.storage_name}: {self._render_type(member.storage_type, (decl.name, member.storage_name))}"
                )
            else:
                raise MojoIRPrintError(f"unsupported StructMember node: {type(member).__name__!r}")

        for initializer in decl.initializers:
            self._render_initializer(
                b,
                decl.name,
                initializer,
                bitfield_names,
                bitfield_storage_types,
            )
        for member in decl.members:
            if isinstance(member, BitfieldGroupMember):
                self._render_bitfield_group_accessors(b, member, (decl.name, member.storage_name))

    def _render_initializer(
        self,
        b: CodeBuilder,
        struct_name: str,
        initializer: Initializer,
        bitfield_names: set[str],
        bitfield_storage_types: dict[str, str],
    ) -> None:
        params = ", ".join(
            f"{self._render_param_name(param.name, i)}: {self._render_type(param.type, (struct_name, self._render_param_name(param.name, i)))}"
            for i, param in enumerate(initializer.params)
        )
        b.add(f"def __init__(out self{', ' if params else ''}{params}):")
        b.indent()
        if bitfield_storage_types:
            for storage_name, storage_type in bitfield_storage_types.items():
                b.add(f"self.{storage_name} = {storage_type}(0)")
        for i, param in enumerate(initializer.params):
            param_name = self._render_param_name(param.name, i)
            if param_name in bitfield_names:
                b.add(f"self.set_{param_name}({param_name})")
            else:
                b.add(f"self.{param_name} = {param_name}")
        b.dedent()

    def _render_bitfield_group_accessors(
        self,
        b: CodeBuilder,
        group: BitfieldGroupMember,
        context: tuple[str, ...],
    ) -> None:
        storage_type = self._render_type(group.storage_type, context)
        for bitfield in group.fields:
            logical_type = self._render_type(
                bitfield.logical_type,
                (*context, bitfield.name or "bitfield"),
            )
            mask_text = self._storage_mask_text(bitfield.bit_width)
            shift = max(0, bitfield.bit_offset - group.byte_offset * 8)
            b.add(f"def {bitfield.name}(self) -> {logical_type}:")
            b.indent()
            b.add(f"var raw = (self.{group.storage_name} >> {shift}) & {storage_type}({mask_text})")
            if bitfield.bool_semantics:
                b.add(f"return raw != {storage_type}(0)")
            elif bitfield.signed and bitfield.bit_width > 0:
                sign_bit_text = hex(1 << (bitfield.bit_width - 1))
                b.add(f"if raw & {storage_type}({sign_bit_text}) != {storage_type}(0):")
                b.indent()
                b.add(f"return {logical_type}(raw | ~{storage_type}({mask_text}))")
                b.dedent()
                b.add(f"return {logical_type}(raw)")
            else:
                b.add(f"return {logical_type}(raw)")
            b.dedent()
            b.add(f"def set_{bitfield.name}(mut self, value: {logical_type}):")
            b.indent()
            if bitfield.bool_semantics:
                b.add(f"var raw_value = {storage_type}(1) if value else {storage_type}(0)")
            else:
                b.add(f"var raw_value = {storage_type}(value) & {storage_type}({mask_text})")
            b.add(f"var clear_mask = ~({storage_type}({mask_text}) << {shift})")
            b.add(
                f"self.{group.storage_name} = (self.{group.storage_name} & clear_mask) | "
                f"((raw_value & {storage_type}({mask_text})) << {shift})"
            )
            b.dedent()

    def _render_alias_decl(self, decl: AliasDecl) -> str:
        b = CodeBuilder()
        b.extend(self._diagnostic_lines(decl.diagnostics))
        if decl.kind == AliasKind.CALLBACK_SIGNATURE:
            fn_type = self._callback_signature_type_for_decl(decl)
            if fn_type is None:
                b.add(f"# callback alias {decl.name}: missing callback signature payload")
            else:
                b.add(
                    f"comptime {decl.name} = {self._render_function_signature(fn_type, (decl.name,))}"
                )
            b.add("")
            return b.render()

        if decl.type_value is not None:
            rhs = self._render_type(decl.type_value, (decl.name,))
            b.add(f"comptime {decl.name} = {rhs}")
        elif decl.const_value is not None:
            rendered = self._render_const_expr(decl.const_value)
            if rendered is None:
                label = "macro" if decl.kind == AliasKind.MACRO_VALUE else "constant"
                b.add(f"# {label} {decl.name}: unsupported constant expression form")
            else:
                b.add(f"comptime {decl.name} = {rendered}")
        else:
            b.add(f"# alias {decl.name}: missing payload")
        b.add("")
        return b.render()

    def _render_function_decl(self, decl: FunctionDecl) -> str:
        b = CodeBuilder()
        b.extend(self._diagnostic_lines(decl.diagnostics))
        params = [
            f"{self._render_param_name(param.name, i)}: {self._render_type(param.type, (decl.name, param.name or f'param{i}'))}"
            for i, param in enumerate(decl.params)
        ]
        params_text = ", ".join(params)
        return_type = self._render_type(decl.return_type, (decl.name, "return"))
        symbol = self._link_symbol(decl.call_target, decl.link_name)
        bracket_inner = ", ".join(
            [f'"{symbol}"', return_type]
            + [
                self._render_type(param.type, (decl.name, param.name or f"param{i}"))
                for i, param in enumerate(decl.params)
            ]
        )
        call_args = ", ".join(
            self._render_param_name(param.name, i) for i, param in enumerate(decl.params)
        )

        if decl.kind == FunctionKind.VARIADIC_STUB:
            b.add("# variadic C function - not callable from thin FFI:")
            b.add(f"# {return_type} {symbol}({params_text}, ...)")
            b.add("")
            return b.render()
        if decl.kind == FunctionKind.NON_REGISTER_RETURN_STUB:
            b.add(
                "# C return type is not RegisterPassable - external_call cannot model this return; bind manually."
            )
            b.add(f"# {return_type} {symbol}({params_text})")
            b.add("")
            return b.render()

        link_mode = self._function_link_mode(decl)
        if link_mode == LinkMode.EXTERNAL_CALL:
            if return_type == "NoneType":
                b.add(f'def {decl.name}({params_text}) abi("C") -> None:')
                b.indent()
                b.add(f"external_call[{bracket_inner}]({call_args})")
            else:
                b.add(f'def {decl.name}({params_text}) abi("C") -> {return_type}:')
                b.indent()
                b.add(f"return external_call[{bracket_inner}]({call_args})")
        else:
            if return_type == "NoneType":
                b.add(f"def {decl.name}({params_text}) raises -> None:")
                b.indent()
                b.add(f"_bindgen_dl().call[{bracket_inner}]({call_args})")
            else:
                b.add(f"def {decl.name}({params_text}) raises -> {return_type}:")
                b.indent()
                b.add(f"return _bindgen_dl().call[{bracket_inner}]({call_args})")
        b.dedent()
        b.add("")
        return b.render() + "\n"

    def _render_global_decl(self, decl: GlobalDecl) -> str:
        b = CodeBuilder()
        b.extend(self._diagnostic_lines(decl.diagnostics))
        value_type = self._render_type(decl.value_type, (decl.name, "value"))
        if decl.kind == GlobalKind.STUB:
            const_kw = "const " if decl.is_const else ""
            b.add(
                f"# global variable {decl.link_name}: {const_kw}{value_type} (manual binding required)"
            )
            b.add("")
            return b.render()

        wrapper = "GlobalConst" if decl.is_const else "GlobalVar"
        link_lit = decl.link_name.replace("\\", "\\\\").replace('"', '\\"')
        b.add(f"# global `{decl.link_name}` -> {value_type}")
        b.add(f'comptime {decl.name} = {wrapper}[T={value_type}, link="{link_lit}"]')
        b.add("")
        return b.render()

    def _render_function_signature(self, fn_type: FunctionType, context: tuple[str, ...]) -> str:
        params = ", ".join(
            f"arg{i}: {self._render_type(param, (*context, f'arg{i}'))}"
            for i, param in enumerate(fn_type.params)
        )
        ret = self._render_type(fn_type.ret, (*context, "return"))
        return f'def ({params}) thin abi("C") -> {ret}'

    def _render_type(self, t: MojoType, context: tuple[str, ...]) -> str:
        if isinstance(t, BuiltinType):
            if t.name == MojoBuiltin.UNSUPPORTED:
                raise MojoIRPrintError("cannot render MojoBuiltin.UNSUPPORTED as valid Mojo")
            if t.name.value.startswith("c_"):
                self._imports.ffi_names.add(t.name.value)
            return t.name.value
        if isinstance(t, NamedType):
            return t.name
        if isinstance(t, PointerType):
            return self._render_pointer_type(t, context)
        if isinstance(t, ArrayType):
            return f"InlineArray[{self._render_type(t.element, (*context, 'element'))}, {t.count}]"
        if isinstance(t, ParametricType):
            if t.base == "SIMD":
                self._imports.needs_simd_import = True
            elif t.base == "ComplexSIMD":
                self._imports.needs_complex_import = True
            elif t.base == "Atomic":
                self._imports.needs_atomic_import = True
            elif t.base == "UnsafeUnion":
                self._imports.ffi_names.add("UnsafeUnion")
            for arg in t.args:
                if arg.startswith("c_"):
                    self._imports.ffi_names.add(arg)
            return f"{t.base}[{', '.join(t.args)}]"
        if isinstance(t, FunctionType):
            return self._render_function_signature(t, context)
        raise MojoIRPrintError(f"unsupported MojoType node: {type(t).__name__!r}")

    def _render_pointer_type(self, t: PointerType, context: tuple[str, ...]) -> str:
        if t.pointee is None:
            self._imports.needs_opaque_imports = True
            origin = (
                self._origin.immut if t.mutability == PointerMutability.IMMUT else self._origin.mut
            )
            ptr_name = (
                "ImmutOpaquePointer"
                if t.mutability == PointerMutability.IMMUT
                else "MutOpaquePointer"
            )
            return f"{ptr_name}[{origin}]"
        if isinstance(t.pointee, FunctionType):
            alias = self._synth_aliases_by_path.get((*context, "callback"))
            if alias is None:
                alias = self._ensure_callback_alias((*context, "callback"), t.pointee)
            origin = (
                self._origin.immut if t.mutability == PointerMutability.IMMUT else self._origin.mut
            )
            return f"UnsafePointer[{alias.name}, {origin}]"
        origin = self._origin.immut if t.mutability == PointerMutability.IMMUT else self._origin.mut
        return f"UnsafePointer[{self._render_type(t.pointee, (*context, 'pointee'))}, {origin}]"

    def _render_const_expr(self, expr: ConstExpr) -> str | None:
        if isinstance(expr, IntLiteral):
            return str(expr.value)
        if isinstance(expr, FloatLiteral):
            return mojo_float_literal_text(expr.value)
        if isinstance(expr, StringLiteral):
            return '"' + expr.value.replace("\\", "\\\\").replace('"', '\\"') + '"'
        if isinstance(expr, CharLiteral):
            return "'" + expr.value.replace("\\", "\\\\").replace("'", "\\'") + "'"
        if isinstance(expr, RefExpr):
            return mojo_ident(expr.name)
        if isinstance(expr, UnaryExpr):
            operand = self._render_const_expr(expr.operand)
            return None if operand is None else f"{expr.op}({operand})"
        if isinstance(expr, BinaryExpr):
            lhs = self._render_const_expr(expr.lhs)
            rhs = self._render_const_expr(expr.rhs)
            return None if lhs is None or rhs is None else f"({lhs} {expr.op} {rhs})"
        if isinstance(expr, CastExpr):
            target_text = self._render_cir_scalar(expr.target)
            if target_text is None:
                return None
            inner = self._render_const_expr(expr.expr)
            return None if inner is None else f"{target_text}({inner})"
        if isinstance(expr, SizeOfExpr):
            target = self._render_cir_scalar(expr.target)
            return None if target is None else f"__builtin_sizeof[{target}]()"
        if isinstance(expr, NullPtrLiteral):
            return None
        return None

    def _render_cir_scalar(self, t: object) -> str | None:
        if isinstance(t, VoidType):
            key: object = "void"
        elif isinstance(t, IntType):
            key = t.int_kind
        elif isinstance(t, FloatType):
            key = t.float_kind
        else:
            return None
        builtin = PRIMITIVE_BUILTINS.get(key)
        if builtin is None or builtin == MojoBuiltin.UNSUPPORTED:
            return None
        if builtin.value.startswith("c_"):
            self._imports.ffi_names.add(builtin.value)
        return builtin.value

    @staticmethod
    def _diagnostic_lines(notes: Iterable[LoweringNote]) -> list[str]:
        lines: list[str] = []
        for note in notes:
            severity = note.severity.value.upper()
            lines.append(f"# {severity}[{note.category}]: {note.message}")
        return lines

    @staticmethod
    def _render_param_name(name: str, index: int) -> str:
        if name.strip():
            return mojo_ident(name)
        return f"a{index}"

    @staticmethod
    def _storage_mask_text(width: int) -> str:
        if width <= 0:
            return "0"
        return hex((1 << width) - 1)

    @staticmethod
    def _link_symbol(call_target: CallTarget, fallback: str) -> str:
        return call_target.symbol or fallback

    def _function_link_mode(self, decl: FunctionDecl) -> LinkMode:
        if (
            decl.call_target.link_mode == LinkMode.EXTERNAL_CALL
            and not decl.call_target.symbol
            and self._module.link_mode != LinkMode.EXTERNAL_CALL
        ):
            return self._module.link_mode
        return decl.call_target.link_mode

    @staticmethod
    def _callback_signature_type_for_decl(decl: AliasDecl) -> FunctionType | None:
        if isinstance(decl.type_value, FunctionType):
            return decl.type_value
        if isinstance(decl.type_value, PointerType) and isinstance(
            decl.type_value.pointee, FunctionType
        ):
            return decl.type_value.pointee
        return None


def render_mojo_module(
    module: MojoModule,
    options: MojoIRPrintOptions | None = None,
) -> str:
    """Render a standalone :class:`MojoModule` to Mojo source."""

    return MojoIRPrinter(options).render(module)


__all__ = [
    "MojoIRPrintError",
    "MojoIRPrinter",
    "MojoIRPrintOptions",
    "render_mojo_module",
]
