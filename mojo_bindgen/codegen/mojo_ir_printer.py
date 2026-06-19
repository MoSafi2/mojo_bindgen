"""Pretty-print finalized MojoIR to Mojo source."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from mojo_bindgen.analysis.common import mojo_float_literal_text, mojo_ident
from mojo_bindgen.ir import (
    AliasDecl,
    AliasKind,
    Array,
    BinaryExpr,
    BitfieldField,
    BitfieldGroupMember,
    BuiltinType,
    CallExpr,
    CallTarget,
    CastExpr,
    CharLiteral,
    ComptimeMember,
    ConstExpr,
    DocComment,
    FlexibleTail,
    FloatLiteral,
    FunctionDecl,
    FunctionKind,
    FunctionPtr,
    GlobalDecl,
    GlobalKind,
    Initializer,
    IntLiteral,
    LinkMode,
    MappingNote,
    ModuleImport,
    MojoBuiltin,
    MojoDecl,
    MojoModule,
    NamedType,
    OpaqueStorageMember,
    PaddingMember,
    Param,
    ParametricBase,
    ParametricType,
    Pointer,
    PointerMutability,
    PointerOrigin,
    RefExpr,
    SizeOfExpr,
    StoredMember,
    StringLiteral,
    StructDecl,
    StructKind,
    SupportDeclKind,
    Type,
    UnaryExpr,
)


@dataclass(frozen=True)
class MojoIRPrintOptions:
    module_comment: bool = True
    emit_doc_comments: bool = True


class MojoIRPrintError(ValueError):
    """Raised when normalized MojoIR cannot be rendered as valid Mojo source."""


def _escape_mojo_string(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace("\0", "\\0")
    )


def _escape_mojo_char(value: str) -> str:
    return _escape_mojo_string(value).replace("'", "\\'")


def _padding_scalar_chunks(byte_offset: int, size_bytes: int) -> list[str]:
    chunks: list[str] = []
    offset = byte_offset
    remaining = size_bytes
    chunk_types = ((8, "UInt64"), (4, "UInt32"), (2, "UInt16"), (1, "UInt8"))
    while remaining > 0:
        for chunk_size, chunk_type in chunk_types:
            if remaining >= chunk_size and offset % chunk_size == 0:
                chunks.append(chunk_type)
                offset += chunk_size
                remaining -= chunk_size
                break
    return chunks


def _clean_doc_comment(doc: DocComment | None) -> list[str]:
    if doc is None or not doc.text.strip():
        return []

    text = doc.text.replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = text.splitlines()
    if not lines:
        return []

    first = lines[0].lstrip()
    if first.startswith("///") or first.startswith("//!"):
        cleaned = [_strip_line_doc_marker(line) for line in lines]
    else:
        cleaned = _strip_block_doc_markers(lines)

    return _dedent_doc_lines(_trim_blank_doc_lines(cleaned))


def _strip_line_doc_marker(line: str) -> str:
    stripped = line.lstrip()
    for marker in ("///", "//!"):
        if stripped.startswith(marker):
            stripped = stripped[len(marker) :]
            if stripped.startswith(" "):
                stripped = stripped[1:]
            return stripped.rstrip()
    return line.rstrip()


def _strip_block_doc_markers(lines: list[str]) -> list[str]:
    out = list(lines)
    if out:
        first = out[0].lstrip()
        for marker in ("/**<", "/*!<", "/**", "/*!"):
            if first.startswith(marker):
                first = first[len(marker) :]
                out[0] = first
                break
    if out and out[-1].rstrip().endswith("*/"):
        out[-1] = out[-1].rstrip()[:-2]

    cleaned: list[str] = []
    for line in out:
        stripped = line.lstrip()
        if stripped.startswith("*"):
            stripped = stripped[1:]
            if stripped.startswith(" "):
                stripped = stripped[1:]
            cleaned.append(stripped.rstrip())
        else:
            cleaned.append(line.rstrip())
    return cleaned


def _trim_blank_doc_lines(lines: list[str]) -> list[str]:
    start = 0
    end = len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return lines[start:end]


def _dedent_doc_lines(lines: list[str]) -> list[str]:
    indents = [len(line) - len(line.lstrip(" ")) for line in lines if line.strip()]
    if not indents:
        return []
    indent = min(indents)
    if indent <= 0:
        return lines
    return [line[indent:] if line.strip() else "" for line in lines]


def _escape_docstring_line(line: str) -> str:
    return line.replace('"""', '\\"\\"\\"')


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


class MojoIRPrinter:
    """Render finalized printer-ready :class:`~mojo_bindgen.ir.MojoModule` to source text."""

    def __init__(self, options: MojoIRPrintOptions | None = None) -> None:
        self._options = options or MojoIRPrintOptions()

    @property
    def options(self) -> MojoIRPrintOptions:
        return self._options

    def render(self, module: MojoModule) -> str:
        parts: list[str] = []
        if self._options.module_comment:
            parts.append(self._render_module_header(module))
        if module.dependencies.imports:
            parts.append(self._render_import_block(module.dependencies.imports))
        support_block = self._render_support_decls(module)
        if support_block:
            parts.append(support_block)
        parts.extend(self._render_decl(decl) for decl in module.decls)
        return "\n\n".join(chunk for chunk in parts if chunk) + ("\n" if parts else "")

    def _render_module_header(self, module: MojoModule) -> str:
        return "\n".join(
            [
                "# Generated by mojo_bindgen - do not edit by hand.",
                f"# source: {module.source_header}",
                f"# library: {module.library}  link_name: {module.link_name}",
                f"# FFI mode: {module.link_mode.value}",
            ]
        )

    @staticmethod
    def _render_import_block(imports: list[ModuleImport]) -> str:
        lines = [f"from {imp.module} import {', '.join(imp.names)}" for imp in imports]
        return "\n".join(lines)

    def _render_support_decls(self, module: MojoModule) -> str:
        chunks: list[str] = []
        for support in module.dependencies.support_decls:
            if support.kind == SupportDeclKind.DL_HANDLE_HELPERS:
                chunks.append(self._render_dl_handle_helper(module))
            elif support.kind == SupportDeclKind.GLOBAL_SYMBOL_HELPERS:
                chunks.append(
                    "struct GlobalVar[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:\n"
                    "    @staticmethod\n"
                    "    def _raw() -> UnsafePointer[Self.T, MutUntrackedOrigin]:\n"
                    "        var opt: Optional[UnsafePointer[Self.T, MutUntrackedOrigin]] = _bindgen_dylib().get_symbol[Self.T](StringSlice(Self.link))\n"
                    "        if not opt:\n"
                    "            abort(\n"
                    "                t\"bindgen: missing C global symbol '{Self.link}' \"\n"
                    "                t\"in dynamic library '{_BINDGEN_LIB_NAME}'\"\n"
                    "            )\n"
                    "        return opt.value()\n"
                    "\n"
                    "    @staticmethod\n"
                    "    def ptr() -> UnsafePointer[Self.T, MutUntrackedOrigin]:\n"
                    "        return rebind[UnsafePointer[Self.T, MutUntrackedOrigin]](Self._raw())\n"
                    "\n"
                    "    @staticmethod\n"
                    "    def load() -> Self.T:\n"
                    "        return Self._raw()[].copy()\n"
                    "\n"
                    "    @staticmethod\n"
                    "    def store(value: Self.T) -> None:\n"
                    "        var p = rebind[UnsafePointer[Self.T, MutUntrackedOrigin]](Self._raw())\n"
                    "        p[] = value.copy()\n"
                    "\n"
                    "struct GlobalConst[T: Copyable & ImplicitlyDestructible, //, link: StaticString]:\n"
                    "    @staticmethod\n"
                    "    def _raw() -> UnsafePointer[Self.T, MutUntrackedOrigin]:\n"
                    "        var opt: Optional[UnsafePointer[Self.T, MutUntrackedOrigin]] = _bindgen_dylib().get_symbol[Self.T](StringSlice(Self.link))\n"
                    "        if not opt:\n"
                    "            abort(\n"
                    "                t\"bindgen: missing C global symbol '{Self.link}' \"\n"
                    "                t\"in dynamic library '{_BINDGEN_LIB_NAME}'\"\n"
                    "            )\n"
                    "        return opt.value()\n"
                    "\n"
                    "    @staticmethod\n"
                    "    def ptr() -> UnsafePointer[Self.T, ImmutUntrackedOrigin]:\n"
                    "        return rebind[UnsafePointer[Self.T, ImmutUntrackedOrigin]](Self._raw())\n"
                    "\n"
                    "    @staticmethod\n"
                    "    def load() -> Self.T:\n"
                    "        return Self._raw()[].copy()"
                )
            else:
                raise MojoIRPrintError(f"unsupported SupportDecl kind: {support.kind!r}")
        return "\n\n".join(chunks)

    @staticmethod
    def _render_dl_handle_helper(module: MojoModule) -> str:
        library_lit = _escape_mojo_string(module.library)
        link_lit = _escape_mojo_string(module.link_name)
        if module.link_mode == LinkMode.EXTERNAL_CALL:
            return (
                f'comptime _BINDGEN_LIB_NAME = "{library_lit}"\n'
                f'comptime _BINDGEN_LINK_NAME = "{link_lit}"\n'
                "\n"
                "def _bindgen_init_dylib() -> OwnedDLHandle:\n"
                "    try:\n"
                "        return OwnedDLHandle(DEFAULT_RTLD)\n"
                "    except e:\n"
                '        abort(t"bindgen: failed to open process dynamic symbol table: {e}")\n'
                "\n"
                'comptime _BINDGEN_DYLIB = _Global["mojo_bindgen/'
                f'{library_lit}", _bindgen_init_dylib]\n'
                "\n" + MojoIRPrinter._render_cached_dl_helpers()
            )
        if module.link_mode == LinkMode.OWNED_DL_HANDLE and module.library_path_hint is not None:
            path_lit = _escape_mojo_string(module.library_path_hint)
            return (
                f'comptime _BINDGEN_LIB_NAME = "{library_lit}"\n'
                f'comptime _BINDGEN_LINK_NAME = "{link_lit}"\n'
                f'comptime _BINDGEN_LIB_PATH: String = "{path_lit}"\n'
                "\n"
                "def _bindgen_init_dylib() -> OwnedDLHandle:\n"
                "    return _find_dylib[_BINDGEN_LIB_NAME](_BINDGEN_LIB_PATH)\n"
                "\n"
                'comptime _BINDGEN_DYLIB = _Global["mojo_bindgen/'
                f'{library_lit}", _bindgen_init_dylib]\n'
                "\n" + MojoIRPrinter._render_cached_dl_helpers()
            )
        return (
            f'comptime _BINDGEN_LIB_NAME = "{library_lit}"\n'
            f'comptime _BINDGEN_LINK_NAME = "{link_lit}"\n'
            "\n"
            "def _bindgen_init_dylib() -> OwnedDLHandle:\n"
            "    return _find_dylib[_BINDGEN_LIB_NAME](\n"
            "        _BINDGEN_LINK_NAME,\n"
            '        "lib" + String(_BINDGEN_LINK_NAME) + ".so",\n'
            '        "lib" + String(_BINDGEN_LINK_NAME) + ".dylib",\n'
            "    )\n"
            "\n"
            'comptime _BINDGEN_DYLIB = _Global["mojo_bindgen/'
            f'{library_lit}", _bindgen_init_dylib]\n'
            "\n" + MojoIRPrinter._render_cached_dl_helpers()
        )

    @staticmethod
    def _render_cached_dl_helpers() -> str:
        return (
            "# Returns a borrowed process-lifetime dynamic library handle; do not close it.\n"
            "def _bindgen_dylib() -> _DLHandle:\n"
            "    var dylib_ptr = _get_global[\n"
            "        _BINDGEN_DYLIB.name,\n"
            "        _BINDGEN_DYLIB._init_wrapper,\n"
            "        _BINDGEN_DYLIB._deinit_wrapper,\n"
            "    ]()\n"
            "    var dylib = unsafe_cast[Type=_BINDGEN_DYLIB.StorageType](dylib_ptr).value()[].borrow()\n"
            "    if not dylib:\n"
            "        abort(t\"bindgen: failed to load dynamic library '{_BINDGEN_LIB_NAME}'\")\n"
            "    return dylib\n"
            "\n"
            "def _bindgen_function[Fn: TrivialRegisterPassable](symbol: StringSlice) -> Fn:\n"
            "    var fn_ptr = _bindgen_dylib().get_symbol[NoneType](symbol)\n"
            "    if not fn_ptr:\n"
            "        abort(\n"
            "            t\"bindgen: missing C function symbol '{symbol}' \"\n"
            "            t\"in dynamic library '{_BINDGEN_LIB_NAME}'\"\n"
            "        )\n"
            "    return UnsafePointer(to=fn_ptr.value()).bitcast[Fn]()[]"
        )

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

    # TODO: Revise traits
    def _render_struct_decl(self, decl: StructDecl) -> str:
        b = CodeBuilder()
        b.extend(self._diagnostic_lines(decl.diagnostics))
        if decl.align_decorator is not None:
            b.add(f"@align({decl.align_decorator})")
        if decl.fieldwise_init:
            b.add("@fieldwise_init")

        traits = list(decl.traits)
        if decl.kind == StructKind.OPAQUE and not traits:
            traits = ["Copyable", "Movable"]
        trait_text = f"({', '.join(traits)})" if traits else ""
        b.add(f"struct {decl.name}{trait_text}:")
        b.indent()
        self._render_docstring(b, decl.doc)
        if decl.kind == StructKind.OPAQUE:
            b.add("pass")
        else:
            self._render_plain_struct_body(b, decl)
        b.dedent()
        return b.render()

    def _render_plain_struct_body(self, b: CodeBuilder, decl: StructDecl) -> None:
        if not decl.members and not decl.comptime_members and not decl.initializers:
            b.add("pass")
            return

        bitfield_names = {
            field.name
            for member in decl.members
            if isinstance(member, BitfieldGroupMember)
            for field in member.fields
        }
        bitfield_storage_types = {
            member.storage_name: self._render_type(member.storage_type)
            for member in decl.members
            if isinstance(member, BitfieldGroupMember)
        }

        for member in decl.members:
            if isinstance(member, StoredMember):
                b.extend(self._doc_comment_lines(member.doc))
                b.add(f"var {member.name}: {self._render_type(member.type)}")
            elif isinstance(member, OpaqueStorageMember):
                b.add(f"var {member.name}: InlineArray[UInt8, {member.size_bytes}]")
            elif isinstance(member, BitfieldGroupMember):
                b.add(f"var {member.storage_name}: {self._render_type(member.storage_type)}")
            else:
                self._render_padding_member(b, member)

        for member in decl.comptime_members:
            self._render_comptime_member(b, member)

        for initializer in decl.initializers:
            self._render_initializer(
                b,
                initializer,
                bitfield_names,
                bitfield_storage_types,
            )
        for member in decl.members:
            if isinstance(member, BitfieldGroupMember):
                self._render_bitfield_group_accessors(b, member)
        if decl.flexible_tail is not None:
            self._render_flexible_tail_helpers(b, decl.name, decl.flexible_tail)

    def _render_initializer(
        self,
        b: CodeBuilder,
        initializer: Initializer,
        bitfield_names: set[str],
        bitfield_storage_types: dict[str, str],
    ) -> None:
        params = ", ".join(
            f"{self._render_param_name(param.name, i)}: {self._render_type(param.type)}"
            for i, param in enumerate(initializer.params)
        )
        b.add(f"def __init__(out self{', ' if params else ''}{params}):")
        b.indent()
        for storage_name, storage_type in bitfield_storage_types.items():
            b.add(f"self.{storage_name} = {storage_type}(0)")
        for i, param in enumerate(initializer.params):
            param_name = self._render_param_name(param.name, i)
            if param_name in bitfield_names:
                b.add(f"self.set_{param_name}({param_name})")
            else:
                b.add(f"self.{param_name} = {param_name}")
        b.dedent()

    @staticmethod
    def _render_padding_member(b: CodeBuilder, member: PaddingMember) -> None:
        chunks = _padding_scalar_chunks(member.byte_offset, member.size_bytes)
        if not chunks:
            return
        if len(chunks) == 1:
            b.add(f"var {member.name}: {chunks[0]}")
            return
        for i, chunk_type in enumerate(chunks):
            b.add(f"var {member.name}_{i}: {chunk_type}")

    def _render_bitfield_group_accessors(
        self,
        b: CodeBuilder,
        group: BitfieldGroupMember,
    ) -> None:
        storage_type = self._render_type(group.storage_type)
        for bitfield in group.fields:
            logical_type = self._render_type(bitfield.logical_type)
            mask_text = self._storage_mask_text(bitfield.bit_width)
            b.extend(self._doc_comment_lines(bitfield.doc))
            b.add(f"def {bitfield.name}(self) -> {logical_type}:")
            b.indent()
            self._render_bitfield_accessor_read(
                b,
                group,
                bitfield,
                logical_type,
                storage_type,
                mask_text,
            )
            b.dedent()
            b.add(f"def set_{bitfield.name}(mut self, value: {logical_type}):")
            b.indent()
            self._render_bitfield_accessor_write(b, group, bitfield, storage_type, mask_text)
            b.dedent()

    def _render_flexible_tail_helpers(
        self,
        b: CodeBuilder,
        struct_name: str,
        tail: FlexibleTail,
    ) -> None:
        elem_type = self._render_type(tail.element_type)
        b.add("@staticmethod")
        b.add(f"def {tail.field_name}_offset() -> UInt:")
        b.indent()
        b.add(f"return {tail.byte_offset}")
        b.dedent()
        b.add("@staticmethod")
        b.add(
            f"def {tail.field_name}_ptr(base: UnsafePointer[{struct_name}, ImmutUntrackedOrigin]) -> UnsafePointer[{elem_type}, ImmutUntrackedOrigin]:"
        )
        b.indent()
        b.add(f"var raw = rebind[UnsafePointer[{elem_type}, ImmutUntrackedOrigin]](base)")
        b.add(f"return raw + {tail.byte_offset}")
        b.dedent()
        b.add("@staticmethod")
        b.add(
            f"def {tail.field_name}_mut_ptr(base: UnsafePointer[{struct_name}, MutUntrackedOrigin]) -> UnsafePointer[{elem_type}, MutUntrackedOrigin]:"
        )
        b.indent()
        b.add(f"var raw = rebind[UnsafePointer[{elem_type}, MutUntrackedOrigin]](base)")
        b.add(f"return raw + {tail.byte_offset}")
        b.dedent()

    def _render_bitfield_accessor_read(
        self,
        b: CodeBuilder,
        group: BitfieldGroupMember,
        bitfield: BitfieldField,
        logical_type: str,
        storage_type: str,
        mask_text: str,
    ) -> None:
        little_shift, big_shift = self._bitfield_shifts(group, bitfield)
        b.add("comptime if is_little_endian():")
        b.indent()
        self._render_bitfield_accessor_read_branch(
            b,
            group.storage_name,
            logical_type,
            storage_type,
            mask_text,
            little_shift,
            bitfield,
        )
        b.dedent()
        b.add("elif is_big_endian():")
        b.indent()
        self._render_bitfield_accessor_read_branch(
            b,
            group.storage_name,
            logical_type,
            storage_type,
            mask_text,
            big_shift,
            bitfield,
        )
        b.dedent()

    def _render_bitfield_accessor_read_branch(
        self,
        b: CodeBuilder,
        storage_name: str,
        logical_type: str,
        storage_type: str,
        mask_text: str,
        shift: int,
        bitfield: BitfieldField,
    ) -> None:
        b.add(f"var raw = (self.{storage_name} >> {shift}) & {storage_type}({mask_text})")
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

    def _render_bitfield_accessor_write(
        self,
        b: CodeBuilder,
        group: BitfieldGroupMember,
        bitfield: BitfieldField,
        storage_type: str,
        mask_text: str,
    ) -> None:
        little_shift, big_shift = self._bitfield_shifts(group, bitfield)
        b.add("comptime if is_little_endian():")
        b.indent()
        self._render_bitfield_accessor_write_branch(
            b,
            group.storage_name,
            storage_type,
            mask_text,
            little_shift,
            bitfield,
        )
        b.dedent()
        b.add("elif is_big_endian():")
        b.indent()
        self._render_bitfield_accessor_write_branch(
            b,
            group.storage_name,
            storage_type,
            mask_text,
            big_shift,
            bitfield,
        )
        b.dedent()

    def _render_bitfield_accessor_write_branch(
        self,
        b: CodeBuilder,
        storage_name: str,
        storage_type: str,
        mask_text: str,
        shift: int,
        bitfield: BitfieldField,
    ) -> None:
        if bitfield.bool_semantics:
            b.add(f"var raw_value = {storage_type}(1) if value else {storage_type}(0)")
        else:
            b.add(f"var raw_value = {storage_type}(value) & {storage_type}({mask_text})")
        b.add(f"var clear_mask = ~({storage_type}({mask_text}) << {shift})")
        b.add(
            f"self.{storage_name} = (self.{storage_name} & clear_mask) | "
            f"((raw_value & {storage_type}({mask_text})) << {shift})"
        )

    def _bitfield_shifts(
        self, group: BitfieldGroupMember, bitfield: BitfieldField
    ) -> tuple[int, int]:
        bit_offset = bitfield.bit_offset - group.byte_offset * 8
        little_shift = max(0, bit_offset)
        big_shift = max(0, group.storage_width_bits - bit_offset - bitfield.bit_width)
        return little_shift, big_shift

    def _render_alias_decl(self, decl: AliasDecl) -> str:
        b = CodeBuilder()
        b.extend(self._doc_comment_lines(decl.doc))
        macro_comment_lines = [
            f"# {note.message}" for note in decl.diagnostics if note.category == "macro_comment"
        ]
        non_macro_notes = [note for note in decl.diagnostics if note.category != "macro_comment"]
        b.extend(self._diagnostic_lines(non_macro_notes))
        if decl.kind == AliasKind.CALLBACK_SIGNATURE:
            if not isinstance(decl.type_value, FunctionPtr):
                raise MojoIRPrintError(
                    f"callback alias {decl.name!r} is missing normalized FunctionPtr payload"
                )
            b.add(f"comptime {decl.name} = {self._render_function_signature(decl.type_value)}")
            return b.render()

        if decl.type_value is not None:
            b.add(f"comptime {decl.name} = {self._render_type(decl.type_value)}")
        elif decl.const_value is not None:
            b.add(f"comptime {decl.name} = {self._render_const_expr(decl.const_value)}")
        elif decl.kind == AliasKind.MACRO_VALUE and macro_comment_lines:
            b.extend(macro_comment_lines)
        else:
            b.add(f"# alias {decl.name}: missing payload")
        return b.render()

    def _render_function_decl(self, decl: FunctionDecl) -> str:
        b = CodeBuilder()
        params = [
            f"{self._render_param_name(param.name, i)}: {self._render_type(param.type)}"
            for i, param in enumerate(decl.params)
        ]
        params_text = ", ".join(params)
        return_type = self._render_type(decl.return_type)
        symbol = self._link_symbol(decl.call_target, decl.link_name)
        symbol_lit = _escape_mojo_string(symbol)
        bracket_inner = ", ".join(
            [f'"{symbol}"', return_type] + [self._render_type(param.type) for param in decl.params]
        )
        fn_type = self._render_c_abi_function_pointer_type(decl)
        call_args = ", ".join(
            self._render_param_name(param.name, i) for i, param in enumerate(decl.params)
        )

        if decl.kind == FunctionKind.VARIADIC_STUB:
            b.extend(self._doc_comment_lines(decl.doc))
            b.extend(self._diagnostic_lines(decl.diagnostics))
            b.add("# variadic C function - not callable from thin FFI:")
            b.add(f"# {return_type} {symbol}({params_text}, ...)")
            return b.render()
        if decl.kind == FunctionKind.NON_REGISTER_RETURN_STUB:
            b.extend(self._doc_comment_lines(decl.doc))
            b.extend(self._diagnostic_lines(decl.diagnostics))
            b.add(
                "# C return type is not RegisterPassable - external_call cannot model this return; bind manually."
            )
            b.add(f"# {return_type} {symbol}({params_text})")
            return b.render()

        b.extend(self._diagnostic_lines(decl.diagnostics))
        if decl.call_target.link_mode == LinkMode.EXTERNAL_CALL:
            if return_type == "NoneType":
                b.add(f'def {decl.name}({params_text}) abi("C") -> None:')
                b.indent()
                self._render_docstring(b, decl.doc)
                b.add(f"external_call[{bracket_inner}]({call_args})")
            else:
                b.add(f'def {decl.name}({params_text}) abi("C") -> {return_type}:')
                b.indent()
                self._render_docstring(b, decl.doc)
                b.add(f"return external_call[{bracket_inner}]({call_args})")
        else:
            if return_type == "NoneType":
                b.add(f"def {decl.name}({params_text}) -> None:")
                b.indent()
                self._render_docstring(b, decl.doc)
                b.add(f'var fn_ = _bindgen_function[{fn_type}](StringSlice("{symbol_lit}"))')
                b.add(f"fn_({call_args})")
            else:
                b.add(f"def {decl.name}({params_text}) -> {return_type}:")
                b.indent()
                self._render_docstring(b, decl.doc)
                b.add(f'var fn_ = _bindgen_function[{fn_type}](StringSlice("{symbol_lit}"))')
                b.add(f"return fn_({call_args})")
        b.dedent()
        return b.render()

    def _render_c_abi_function_pointer_type(self, decl: FunctionDecl) -> str:
        params = ", ".join(self._render_type(param.type) for param in decl.params)
        return_type = self._render_type(decl.return_type)
        return f'def({params}) thin abi("C") -> {return_type}'

    def _render_global_decl(self, decl: GlobalDecl) -> str:
        b = CodeBuilder()
        b.extend(self._doc_comment_lines(decl.doc))
        b.extend(self._diagnostic_lines(decl.diagnostics))
        value_type = self._render_type(decl.value_type)
        if decl.kind == GlobalKind.STUB:
            if (
                isinstance(decl.value_type, ParametricType)
                and decl.value_type.base == ParametricBase.ATOMIC
            ):
                b.add(
                    f"# global variable {decl.link_name}: {value_type} (atomic global requires manual binding (use Atomic APIs on a pointer))"
                )
            else:
                const_kw = "const " if decl.is_const else ""
                b.add(
                    f"# global variable {decl.link_name}: {const_kw}{value_type} (manual binding required)"
                )
            return b.render()

        wrapper = "GlobalConst" if decl.is_const else "GlobalVar"
        link_lit = decl.link_name.replace("\\", "\\\\").replace('"', '\\"')
        b.add(f"# global `{decl.link_name}` -> {value_type}")
        b.add(f'comptime {decl.name} = {wrapper}[T={value_type}, link="{link_lit}"]')
        return b.render()

    def _render_comptime_member(self, b: CodeBuilder, member: ComptimeMember) -> None:
        if member.type_value is not None:
            b.add(f"comptime {member.name} = {self._render_type(member.type_value)}")
            return
        if member.const_value is not None:
            b.add(f"comptime {member.name} = {self._render_const_expr(member.const_value)}")
            return
        b.add(f"# comptime {member.name}: missing payload")

    def _render_type(self, t: Type) -> str:
        if isinstance(t, BuiltinType):
            if t.name == MojoBuiltin.UNSUPPORTED:
                raise MojoIRPrintError("cannot render MojoBuiltin.UNSUPPORTED as valid Mojo")
            return t.name.value
        if isinstance(t, NamedType):
            return t.name
        if isinstance(t, Pointer):
            return self._render_pointer_type(t)
        if isinstance(t, Array):
            if t.size is None:
                raise MojoIRPrintError("cannot render array type without a fixed size")
            return f"InlineArray[{self._render_type(t.element)}, {t.size}]"
        if isinstance(t, ParametricType):
            args = ", ".join(self._render_parametric_arg(arg) for arg in t.args)
            return f"{t.base.value}[{args}]"
        if isinstance(t, FunctionPtr):
            return self._render_function_signature(t)
        raise MojoIRPrintError(f"unsupported Type node: {type(t).__name__!r}")

    def _render_pointer_type(self, t: Pointer) -> str:
        if t.pointee is None:
            ptr_name = (
                "ImmutOpaquePointer"
                if t.mutability == PointerMutability.IMMUT
                else "MutOpaquePointer"
            )
            rendered = f"{ptr_name}[{self._origin_name(t.origin, t.mutability)}]"
        else:
            rendered = (
                f"UnsafePointer[{self._render_type(t.pointee)}, "
                f"{self._origin_name(t.origin, t.mutability)}]"
            )
        return f"Optional[{rendered}]" if t.nullable else rendered

    def _render_parametric_arg(self, arg: object) -> str:
        from mojo_bindgen.ir import ConstArg, DTypeArg, NameArg, TypeArg

        if isinstance(arg, DTypeArg):
            return arg.value
        if isinstance(arg, ConstArg):
            return str(arg.value)
        if isinstance(arg, NameArg):
            return arg.value
        if isinstance(arg, TypeArg):
            return self._render_type(arg.type)
        raise MojoIRPrintError(f"unsupported parametric argument node: {type(arg).__name__!r}")

    def _render_function_signature(self, function_type: FunctionPtr) -> str:
        params = ", ".join(
            f"{self._render_function_param_name(param, i)}: {self._render_type(param.type)}"
            for i, param in enumerate(function_type.params)
        )
        ret = self._render_signature_return_type(function_type.ret)
        parts = ["def", f"({params})"]
        if function_type.thin:
            parts.append("thin")
        if function_type.abi:
            parts.append(f'abi("{function_type.abi}")')
        if function_type.raises:
            parts.append("raises")
        parts.extend(["->", ret])
        return " ".join(parts)

    def _render_signature_return_type(self, t: Type) -> str:
        rendered = self._render_type(t)
        return "None" if rendered == "NoneType" else rendered

    def _render_const_expr(self, expr: ConstExpr) -> str:
        if isinstance(expr, IntLiteral):
            return str(expr.value)
        if isinstance(expr, FloatLiteral):
            return mojo_float_literal_text(str(expr.value))
        if isinstance(expr, StringLiteral):
            return '"' + _escape_mojo_string(expr.value) + '"'
        if isinstance(expr, CharLiteral):
            return "'" + _escape_mojo_char(expr.value) + "'"
        if isinstance(expr, RefExpr):
            return expr.name
        if isinstance(expr, UnaryExpr):
            return f"{expr.op}({self._render_const_expr(expr.operand)})"
        if isinstance(expr, BinaryExpr):
            lhs = self._render_const_expr(expr.lhs)
            rhs = self._render_const_expr(expr.rhs)
            return f"({lhs} {expr.op} {rhs})"
        if isinstance(expr, CastExpr):
            return f"{self._render_type(expr.target)}({self._render_const_expr(expr.expr)})"
        if isinstance(expr, CallExpr):
            args = ", ".join(self._render_const_expr(arg) for arg in expr.args)
            return f"{self._render_const_expr(expr.callee)}({args})"
        if isinstance(expr, SizeOfExpr):
            return f"size_of[{self._render_type(expr.target)}]()"
        raise MojoIRPrintError(f"unsupported ConstExpr node: {type(expr).__name__!r}")

    @staticmethod
    def _diagnostic_lines(notes: Iterable[MappingNote]) -> list[str]:
        return [
            f"# {note.severity.value.upper()}[{note.category}]: {note.message}" for note in notes
        ]

    def _doc_comment_lines(self, doc: DocComment | None) -> list[str]:
        if not self._options.emit_doc_comments:
            return []
        lines = _clean_doc_comment(doc)
        if not lines:
            return []
        return ["#" if not line else f"# {line}" for line in lines]

    def _render_docstring(self, b: CodeBuilder, doc: DocComment | None) -> None:
        if not self._options.emit_doc_comments:
            return
        lines = _clean_doc_comment(doc)
        if not lines:
            return
        b.add('"""')
        for line in lines:
            b.add(_escape_docstring_line(line))
        b.add('"""')

    @staticmethod
    def _render_param_name(name: str, index: int) -> str:
        if name.strip():
            return mojo_ident(name)
        return f"a{index}"

    @staticmethod
    def _render_function_param_name(param: Param, index: int) -> str:
        if param.name.strip():
            return mojo_ident(param.name, fallback=f"arg{index}")
        return f"arg{index}"

    @staticmethod
    def _origin_name(origin: PointerOrigin, mutability: PointerMutability) -> str:
        if origin == PointerOrigin.ANY:
            return (
                "ImmutUnsafeAnyOrigin"
                if mutability == PointerMutability.IMMUT
                else "MutUnsafeAnyOrigin"
            )
        return (
            "ImmutUntrackedOrigin"
            if mutability == PointerMutability.IMMUT
            else "MutUntrackedOrigin"
        )

    @staticmethod
    def _storage_mask_text(width: int) -> str:
        if width <= 0:
            return "0"
        return hex((1 << width) - 1)

    @staticmethod
    def _link_symbol(call_target: CallTarget, fallback: str) -> str:
        return call_target.symbol or fallback


def render_mojo_module(
    module: MojoModule,
    options: MojoIRPrintOptions | None = None,
) -> str:
    """Render a finalized :class:`MojoModule` to Mojo source."""

    return MojoIRPrinter(options).render(module)


__all__ = [
    "MojoIRPrintError",
    "MojoIRPrinter",
    "MojoIRPrintOptions",
    "render_mojo_module",
]
