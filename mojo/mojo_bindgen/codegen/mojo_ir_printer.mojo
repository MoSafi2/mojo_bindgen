"""Print finalized target IR without consulting source declarations."""
from std.memory import ArcPointer
from ..ir import *
from ..analysis.mojo.validate_finalized import validate_finalized_mojo_module
from .normalize_mojo_module import required_module_dependencies
from ..analysis.common import mojo_ident, strip_whitespace, mojo_float_literal_text, quoted
from .._numbers import float_text, mask_text, sign_bit_text
from .mojo_support_templates import (
    escape_mojo_string,
    render_dl_handle_helpers,
    render_global_symbol_helpers,
    render_variadic_helpers,
)


struct MojoIRPrintOptions(Copyable, Movable):
    var module_comment: Bool
    var emit_doc_comments: Bool

    def __init__(out self, module_comment: Bool = True, emit_doc_comments: Bool = True):
        self.module_comment = module_comment
        self.emit_doc_comments = emit_doc_comments


struct CodeBuilder(Copyable, Movable):
    var lines: List[String]
    var level: Int

    def __init__(out self):
        self.lines = List[String]()
        self.level = 0

    def indent(mut self):
        self.level += 1

    def dedent(mut self):
        self.level = max(0, self.level - 1)

    def add(mut self, line: String):
        self.lines.append("    " * self.level + line)

    def render(self) -> String:
        return "\n".join(self.lines)


def _slice(value: String, start: Int) -> String:
    return String(value[byte=start:])


def _lstrip(value: String) -> String:
    var trimmed = strip_whitespace(value)
    if not trimmed:
        return String()
    var pos = value.find(trimmed)
    return String(value[byte=pos:])


def _rstrip(value: String) -> String:
    var trimmed = strip_whitespace(value)
    if not trimmed:
        return String()
    var start = value.find(trimmed)
    return String(value[byte = : start + trimmed.byte_length()])


def _clean_doc(doc: Optional[DocComment]) -> List[String]:
    var result = List[String]()
    if not doc:
        return result^
    var text = strip_whitespace(doc.value().text.replace("\r\n", "\n").replace("\r", "\n"))
    if not text:
        return result^
    var lines = List[String]()
    for line in _splitlines(text):
        lines.append(String(line))
    var line_doc = _lstrip(String(lines[0])).startswith("///") or _lstrip(
        String(lines[0])
    ).startswith("//!")
    if not line_doc:
        var first = _lstrip(String(lines[0]))
        for marker in [String("/**<"), String("/*!<"), String("/**"), String("/*!")]:
            if first.startswith(marker):
                first = _slice(first, marker.byte_length())
                break
        lines[0] = first
        var last = _rstrip(String(lines[len(lines) - 1]))
        if last.endswith("*/"):
            lines[len(lines) - 1] = String(last[byte = : last.byte_length() - 2])
    for line in lines:
        var original = String(line)
        var value = _lstrip(original)
        if line_doc:
            if value.startswith("///") or value.startswith("//!"):
                value = _slice(value, 3)
                if value.startswith(" "):
                    value = _slice(value, 1)
            else:
                value = original
        elif value.startswith("*"):
            value = _slice(value, 1)
            if value.startswith(" "):
                value = _slice(value, 1)
        else:
            value = original
        result.append(_rstrip(value))
    while result and not strip_whitespace(result[0]):
        _ = result.pop(0)
    while result and not strip_whitespace(result[len(result) - 1]):
        _ = result.pop()
    var indent = Int.MAX
    for line in result:
        if strip_whitespace(line):
            var count = 0
            for ch in line.as_bytes():
                if ch != 32:
                    break
                count += 1
            indent = min(indent, count)
    if indent > 0 and indent != Int.MAX:
        for i in range(len(result)):
            result[i] = String(result[i][byte=indent:]) if strip_whitespace(result[i]) else String()
    return result^


def _param_name(name: String, index: Int, callback: Bool = False) -> String:
    if strip_whitespace(name):
        return mojo_ident(name, "arg" + String(index) if callback else String("field"))
    return (String("arg") if callback else String("a")) + String(index)


def _origin(origin: PointerOrigin, mutability: PointerMutability) -> String:
    return (String("Imm") if mutability == PointerMutability.IMMUT else String("Mut")) + (
        String("UnsafeAnyOrigin") if origin == PointerOrigin.ANY else String("UntrackedOrigin")
    )


def render_comment_type(t: MojoType) -> String:
    try:
        return render_type(t)
    except:
        return "<unsupported>"


def render_type(t: MojoType) raises -> String:
    match t:
        case .opaque_storage_type(_):
            raise Error("opaque storage must be normalized before printing")
        case .builtin_type(v):
            if v.name == MojoBuiltin.UNSUPPORTED:
                raise Error("cannot render MojoBuiltin.UNSUPPORTED as valid Mojo")
            return v.name.value()
        case .named_type(v):
            return v.name.copy()
        case .mojo_pointer(v):
            var inner: String
            if v.pointee:
                inner = (
                    "Pointer["
                    + render_type(v.pointee.value().ptr()[])
                    + ", "
                    + _origin(v.origin, v.mutability)
                    + "]"
                )
            else:
                inner = (
                    "OpaquePointer[mut="
                    + (
                        String("False") if v.mutability
                        == PointerMutability.IMMUT else String("True")
                    )
                    + ", "
                    + _origin(v.origin, v.mutability)
                    + "]"
                )
            return "Optional[" + inner + "]" if v.nullable else inner^
        case .mojo_array(v):
            return "Array[" + render_type(v.element.ptr()[]) + ", " + String(v.size) + "]"
        case .parametric_type(v):
            var args = List[String]()
            for arg in v.args:
                match arg:
                    case .d_type_arg(a):
                        args.append(a.value)
                    case .const_arg(a):
                        args.append(a.value.digits)
                    case .name_arg(a):
                        args.append(a.value)
                    case .type_arg(a):
                        args.append(render_type(a.type.ptr()[]))
            return v.base.value() + "[" + ", ".join(args) + "]"
        case .mojo_function_ptr(v):
            return _signature(v)


def _signature(v: MojoFunctionPtr) raises -> String:
    var params = List[String]()
    for i in range(len(v.params)):
        params.append(
            _param_name(v.params[i].name, i, True) + ": " + render_type(v.params[i].type.ptr()[])
        )
    var parts = List[String]()
    parts.append("def")
    parts.append("(" + ", ".join(params) + ")")
    if v.thin:
        parts.append("thin")
    if v.abi:
        parts.append('abi("' + v.abi + '")')
    if v.raises_error:
        parts.append("raises")
    var ret = render_type(v.ret.ptr()[])
    parts.append("->")
    parts.append("None" if ret == "NoneType" else ret)
    return " ".join(parts)


def render_const_expr(expr: MojoConstExpr) raises -> String:
    match expr:
        case .int_literal(v):
            return v.value.digits.copy()
        case .mojo_float_literal(v):
            return mojo_float_literal_text(float_text(v.value))
        case .string_literal(v):
            return '"' + escape_mojo_string(v.value) + '"'
        case .char_literal(v):
            return "'" + escape_mojo_string(v.value).replace("'", "\\'") + "'"
        case .mojo_ref_expr(v):
            return v.name.copy()
        case .mojo_unary_expr(v):
            return v.op + "(" + render_const_expr(v.operand.ptr()[]) + ")"
        case .mojo_binary_expr(v):
            return (
                "("
                + render_const_expr(v.lhs.ptr()[])
                + " "
                + v.op
                + " "
                + render_const_expr(v.rhs.ptr()[])
                + ")"
            )
        case .mojo_cast_expr(v):
            return render_type(v.target.ptr()[]) + "(" + render_const_expr(v.expr.ptr()[]) + ")"
        case .mojo_call_expr(v):
            var args = List[String]()
            for arg in v.args:
                args.append(render_const_expr(arg.ptr()[]))
            return render_const_expr(v.callee.ptr()[]) + "(" + ", ".join(args) + ")"
        case .mojo_size_of_expr(v):
            return "size_of[" + render_type(v.target.ptr()[]) + "]()"


def _diagnostics(mut b: CodeBuilder, notes: List[MappingNote]):
    for note in notes:
        b.add("# " + note.severity.value().upper() + "[" + note.category + "]: " + note.message)


struct MojoIRPrinter(Copyable, Movable):
    var options: MojoIRPrintOptions

    def __init__(out self, options: MojoIRPrintOptions = MojoIRPrintOptions()):
        self.options = options.copy()

    def _doc(self, mut b: CodeBuilder, doc: Optional[DocComment], as_string: Bool = False):
        if not self.options.emit_doc_comments:
            return
        var lines = _clean_doc(doc)
        if not lines:
            return
        if as_string:
            b.add('"""')
        for line in lines:
            if as_string:
                b.add(line.replace("\\", "\\\\").replace('"""', '\\"\\"\\"'))
            else:
                b.add("# " + line if line else String("#"))
        if as_string:
            b.add('"""')

    def render(self, module: MojoModule) raises -> String:
        validate_finalized_mojo_module(module, required_module_dependencies(module))
        var parts = List[String]()
        if self.options.module_comment:
            parts.append(
                "# Generated by mojo_bindgen - do not edit by hand.\n# Requires Mojo 1.2 or later (1.x).\n# source: "
                + module.source_header
                + "\n# library: "
                + module.library
                + "  link_name: "
                + module.link_name
                + "\n# FFI mode: "
                + module.link_mode.value()
            )
        var imports = List[String]()
        for imp in module.dependencies.imports:
            imports.append("from " + imp.module + " import " + ", ".join(imp.names))
        if imports:
            parts.append("\n".join(imports))
        var helpers = List[String]()
        for support in module.dependencies.support_decls:
            if support.kind == SupportDeclKind.DL_HANDLE_HELPERS:
                helpers.append(render_dl_handle_helpers(module))
            elif support.kind == SupportDeclKind.GLOBAL_SYMBOL_HELPERS:
                helpers.append(render_global_symbol_helpers())
            elif support.kind == SupportDeclKind.VARIADIC_HELPERS:
                helpers.append(render_variadic_helpers())
        if helpers:
            parts.append("\n\n".join(helpers))
        for decl in module.decls:
            var text: String
            match decl:
                case .struct_decl(v):
                    text = self._struct(v)
                case .alias_decl(v):
                    text = self._alias(v)
                case .function_decl(v):
                    text = self._function(v)
                case .global_decl(v):
                    text = self._global(v)
            parts.append(text^)
        var nonempty = List[String]()
        for part in parts:
            if part:
                nonempty.append(part)
        return "\n\n".join(nonempty) + ("\n" if parts else String())

    def _alias(self, decl: AliasDecl) raises -> String:
        var b = CodeBuilder()
        self._doc(b, decl.doc)
        var comments = List[String]()
        var notes = List[MappingNote]()
        for note in decl.diagnostics:
            if note.category == "macro_comment":
                comments.append("# " + note.message)
            else:
                notes.append(note.copy())
        _diagnostics(b, notes)
        if decl.kind == AliasKind.CALLBACK_SIGNATURE:
            if decl.type_value:
                match decl.type_value.value().ptr()[]:
                    case .mojo_function_ptr(v):
                        b.add("comptime " + decl.name + " = " + _signature(v))
                        return b.render()
                    case _:
                        pass
            raise Error(
                "callback alias " + quoted(decl.name) + " is missing normalized FunctionPtr payload"
            )
        if decl.type_value:
            b.add("comptime " + decl.name + " = " + render_type(decl.type_value.value().ptr()[]))
        elif decl.const_value:
            b.add(
                "comptime "
                + decl.name
                + " = "
                + render_const_expr(decl.const_value.value().ptr()[])
            )
        elif decl.kind == AliasKind.MACRO_VALUE and comments:
            for line in comments:
                b.add(line)
        else:
            b.add("# alias " + decl.name + ": missing payload")
        return b.render()

    def _global(self, decl: GlobalDecl) raises -> String:
        var b = CodeBuilder()
        self._doc(b, decl.doc)
        _diagnostics(b, decl.diagnostics)
        var value = render_comment_type(
            decl.value_type[]
        ) if decl.kind == GlobalKind.STUB else render_type(decl.value_type[])
        if decl.kind == GlobalKind.STUB:
            var atomic = False
            match decl.value_type.ptr()[]:
                case .parametric_type(v):
                    atomic = v.base == ParametricBase.ATOMIC
                case _:
                    pass
            if atomic:
                b.add(
                    "# global variable "
                    + decl.link_name
                    + ": "
                    + value
                    + " (atomic global requires manual binding (use Atomic APIs on a pointer))"
                )
            else:
                b.add(
                    "# global variable "
                    + decl.link_name
                    + ": "
                    + ("const " if decl.is_const else String())
                    + value
                    + " (manual binding required)"
                )
        else:
            b.add("# global `" + decl.link_name + "` -> " + value)
            b.add(
                "comptime "
                + decl.name
                + " = "
                + ("GlobalConst" if decl.is_const else String("GlobalVar"))
                + "[T="
                + value
                + ', link="'
                + decl.link_name.replace("\\", "\\\\").replace('"', '\\"')
                + '"]'
            )
        return b.render()

    def _function(self, decl: FunctionDecl) raises -> String:
        var b = CodeBuilder()
        var callable = (
            decl.kind == FunctionKind.WRAPPER or decl.kind == FunctionKind.EXTERN_DECLARATION
        )
        var names = List[String]()
        var params = List[String]()
        var types = List[String]()
        for i in range(len(decl.params)):
            var name = _param_name(decl.params[i].name, i)
            var t = render_type(decl.params[i].type[]) if callable else render_comment_type(
                decl.params[i].type[]
            )
            names.append(name)
            params.append(name + ": " + t)
            types.append(t)
        var params_text = ", ".join(params)
        var ret = render_type(decl.return_type[]) if callable else render_comment_type(
            decl.return_type[]
        )
        var symbol = decl.call_target.symbol if decl.call_target.symbol else decl.link_name
        var escaped = escape_mojo_string(symbol)
        if decl.kind == FunctionKind.EXTERN_DECLARATION:
            _diagnostics(b, decl.diagnostics)
            b.add('@extern("' + escaped + '")')
            b.add("def " + decl.name + "(" + params_text + ') abi("C") -> ' + ret + ":")
            b.indent()
            self._doc(b, decl.doc, True)
            b.add("...")
            return b.render()
        if (
            decl.kind == FunctionKind.ABI_STUB
            or decl.kind == FunctionKind.VARIADIC_STUB
            or decl.kind == FunctionKind.DIRECTIVE_STUB
            or decl.kind == FunctionKind.NON_REGISTER_RETURN_STUB
        ):
            self._doc(b, decl.doc)
            _diagnostics(b, decl.diagnostics)
            if decl.kind == FunctionKind.VARIADIC_STUB:
                b.add(
                    "# variadic C function - OwnedDLHandle does not expose variadic ABI metadata:"
                )
                b.add("# " + ret + " " + symbol + "(" + params_text + ", ...)")
            else:
                if decl.kind == FunctionKind.NON_REGISTER_RETURN_STUB:
                    b.add(
                        "# C return type is not RegisterPassable - this binding requires manual handling."
                    )
                else:
                    var directives = List[String]()
                    if decl.attrs.inline_disposition == InlineDisposition.INLINE:
                        directives.append("inline")
                    elif decl.attrs.inline_disposition == InlineDisposition.EXTERN_INLINE:
                        directives.append("extern inline")
                    if decl.attrs.is_noreturn:
                        directives.append("noreturn")
                    if directives:
                        b.add(
                            "# C function declaration carries source directives that are not emitted as a callable wrapper:"
                        )
                        b.add("# source directives: " + ", ".join(directives))
                    else:
                        b.add("# C function declaration is not emitted as a callable wrapper:")
                b.add("# " + ret + " " + symbol + "(" + params_text + ")")
            return b.render()
        if decl.num_fixed_args:
            return self._variadic(decl, escaped, ret)
        _diagnostics(b, decl.diagnostics)
        var signature_ret = String("None") if ret == "NoneType" else ret
        var args = ", ".join(names)
        if decl.call_target.link_mode == LinkMode.EXTERNAL_CALL:
            b.add("def " + decl.name + "(" + params_text + ') abi("C") -> ' + signature_ret + ":")
            b.indent()
            self._doc(b, decl.doc, True)
            var inner = List[String]()
            inner.append('"' + symbol + '"')
            inner.append(ret)
            for t in types:
                inner.append(t)
            b.add(
                (String() if ret == "NoneType" else String("return "))
                + "external_call["
                + ", ".join(inner)
                + "]("
                + args
                + ")"
            )
        else:
            var fn_local = _unique("_bindgen_c_fn", names)
            var owner = _unique("_bindgen_owner", names)
            var error = _unique("_bindgen_error", names)
            b.add("def " + decl.name + "(" + params_text + ") -> " + signature_ret + ":")
            b.indent()
            self._doc(b, decl.doc, True)
            b.add("var " + owner + " = _bindgen_dylib()")
            b.add("try:")
            b.indent()
            b.add(
                "var "
                + fn_local
                + " = "
                + owner
                + "[].get_function["
                + ret
                + ']("'
                + escaped
                + '")'
            )
            b.add(
                (String() if ret == "NoneType" else String("return ")) + fn_local + "(" + args + ")"
            )
            b.dedent()
            b.add("except " + error + ":")
            b.indent()
            b.add(
                "abort(t\"bindgen: failed C function symbol '"
                + escaped
                + "' in dynamic library '{_BINDGEN_LIB_NAME}': {"
                + error
                + '}")'
            )
            b.dedent()
        b.dedent()
        return b.render()

    def _variadic(self, decl: FunctionDecl, symbol: String, ret: String) raises -> String:
        var b = CodeBuilder()
        _diagnostics(b, decl.diagnostics)
        var name = decl.name.copy()
        var count = String(decl.num_fixed_args.value())
        b.add(
            "def "
            + name
            + "[*_BindgenArgs: AnyType](*args: *_BindgenArgs) -> "
            + ("None" if ret == "NoneType" else ret)
            + ":"
        )
        b.indent()
        self._doc(b, decl.doc, True)
        b.add(
            "comptime assert _BindgenArgs.length >= "
            + count
            + ', "'
            + name
            + ': missing fixed C arguments"'
        )
        b.add("comptime if _BindgenArgs.length >= " + count + ":")
        b.indent()
        for i in range(len(decl.params)):
            b.add(
                "comptime assert _BindgenArgs["
                + String(i)
                + "] == "
                + render_type(decl.params[i].type.ptr()[])
                + ', "'
                + name
                + ": fixed argument "
                + String(i)
                + ' must have its declared C type"'
            )
        b.add("comptime for i in range(" + count + ", _BindgenArgs.length):")
        b.indent()
        b.add("_bindgen_check_vararg[_BindgenArgs[i]]()")
        b.dedent()
        b.add(
            (String() if ret == "NoneType" else String("return "))
            + 'external_call["'
            + symbol
            + '", '
            + ret
            + ", num_fixed_args="
            + count
            + "](*args)"
        )
        b.dedent()
        if ret != "NoneType":
            b.add("else:")
            b.indent()
            b.add('abort("bindgen: invalid variadic arity")')
            b.dedent()
        b.dedent()
        return b.render()

    def _struct(self, decl: StructDecl) raises -> String:
        var b = CodeBuilder()
        _diagnostics(b, decl.diagnostics)
        if decl.align_decorator:
            b.add("@align(" + String(decl.align_decorator.value()) + ")")
        if decl.fieldwise_init:
            b.add("@fieldwise_init")
        var traits = List[String]()
        for item in decl.traits:
            traits.append(item.value())
        b.add(
            "struct "
            + decl.name
            + ("(" + ", ".join(traits) + ")" if decl.traits else String())
            + ":"
        )
        b.indent()
        self._doc(b, decl.doc, True)
        if decl.kind == StructKind.OPAQUE or (
            not decl.members and not decl.comptime_members and not decl.initializers
        ):
            b.add("pass")
        else:
            var bitnames = Dict[String, Bool]()
            var storage = List[Tuple[String, String]]()
            for member in decl.members:
                match member:
                    case .stored_member(v):
                        self._doc(b, v.doc)
                        b.add("var " + v.name + ": " + render_type(v.type.ptr()[]))
                    case .opaque_storage_member(v):
                        b.add("var " + v.name + ": Array[UInt8, " + String(v.size_bytes) + "]")
                    case .padding_member(v):
                        _padding(b, v)
                    case .bitfield_group_member(v):
                        var t = render_type(v.storage_type.ptr()[])
                        b.add("var " + v.storage_name + ": " + t)
                        storage.append((v.storage_name.copy(), t^))
                        for f in v.fields:
                            bitnames[f.name] = True
            for member in decl.comptime_members:
                if member.type_value:
                    b.add(
                        "comptime "
                        + member.name
                        + " = "
                        + render_type(member.type_value.value().ptr()[])
                    )
                elif member.const_value:
                    b.add(
                        "comptime "
                        + member.name
                        + " = "
                        + render_const_expr(member.const_value.value().ptr()[])
                    )
                else:
                    b.add("# comptime " + member.name + ": missing payload")
            for init in decl.initializers:
                var params = List[String]()
                for i in range(len(init.params)):
                    params.append(
                        _param_name(init.params[i].name, i)
                        + ": "
                        + render_type(init.params[i].type.ptr()[])
                    )
                b.add(
                    "def __init__(out self: Self"
                    + (", " + ", ".join(params) if params else String())
                    + "):"
                )
                b.indent()
                for s in storage:
                    b.add("self." + s[0] + " = " + s[1] + "(0)")
                for i in range(len(init.params)):
                    var name = _param_name(init.params[i].name, i)
                    b.add(
                        "self.set_" + name + "(" + name + ")" if name
                        in bitnames else "self." + name + " = " + name
                    )
                b.dedent()
            for member in decl.members:
                match member:
                    case .bitfield_group_member(v):
                        self._bitfields(b, v)
                    case _:
                        pass
            if decl.flexible_tail:
                _tail(b, decl.name, decl.flexible_tail.value())
        b.dedent()
        return b.render()

    def _bitfields(self, mut b: CodeBuilder, group: BitfieldGroupMember) raises:
        var storage = render_type(group.storage_type.ptr()[])
        for field in group.fields:
            var logical = render_type(field.logical_type.ptr()[])
            var mask = mask_text(field.bit_width) if field.bit_width > 0 else String("0")
            var offset = field.bit_offset - group.byte_offset * 8
            var shifts = [
                max(0, group.storage_width_bits - offset - field.bit_width),
                max(0, offset),
            ]
            self._doc(b, field.doc)
            b.add("def " + field.name + "(self: Self) -> " + logical + ":")
            b.indent()
            for i in range(2):
                b.add("comptime if Endian.native() == Endian.big:" if i == 0 else String("else:"))
                b.indent()
                b.add(
                    "var raw = (self."
                    + group.storage_name
                    + " >> "
                    + String(shifts[i])
                    + ") & "
                    + storage
                    + "("
                    + mask
                    + ")"
                )
                if field.bool_semantics:
                    b.add("return raw != " + storage + "(0)")
                else:
                    if field.signed and field.bit_width > 0:
                        b.add(
                            "if raw & "
                            + storage
                            + "("
                            + sign_bit_text(field.bit_width)
                            + ") != "
                            + storage
                            + "(0):"
                        )
                        b.indent()
                        b.add("return " + logical + "(raw | ~" + storage + "(" + mask + "))")
                        b.dedent()
                    b.add("return " + logical + "(raw)")
                b.dedent()
            b.dedent()
            b.add("def set_" + field.name + "(mut self: Self, value: " + logical + "):")
            b.indent()
            for i in range(2):
                b.add("comptime if Endian.native() == Endian.big:" if i == 0 else String("else:"))
                b.indent()
                b.add(
                    "var raw_value = "
                    + storage
                    + "(1) if value else "
                    + storage
                    + "(0)" if field.bool_semantics else "var raw_value = "
                    + storage
                    + "(value) & "
                    + storage
                    + "("
                    + mask
                    + ")"
                )
                b.add(
                    "var clear_mask = ~(" + storage + "(" + mask + ") << " + String(shifts[i]) + ")"
                )
                b.add(
                    "self."
                    + group.storage_name
                    + " = (self."
                    + group.storage_name
                    + " & clear_mask) | ((raw_value & "
                    + storage
                    + "("
                    + mask
                    + ")) << "
                    + String(shifts[i])
                    + ")"
                )
                b.dedent()
            b.dedent()


def _unique(base: String, names: List[String]) -> String:
    var result = base.copy()
    var suffix = 0
    while result in names:
        suffix += 1
        result = base + "_" + String(suffix)
    return result^


def _padding(mut b: CodeBuilder, member: PaddingMember) raises:
    var width = member.storage_width_bytes
    if (width != 1 and width != 2 and width != 4 and width != 8) or width != member.size_bytes:
        raise Error("unresolved padding in finalized MojoIR")
    b.add("var " + member.name + ": UInt" + String(width * 8))


def _tail(mut b: CodeBuilder, name: String, tail: FlexibleTail) raises:
    var elem = render_type(tail.element_type.ptr()[])
    b.add("@staticmethod")
    b.add("def " + tail.field_name + "_offset() -> UInt:")
    b.indent()
    b.add("return " + String(tail.byte_offset))
    b.dedent()
    for origin in [String("ImmUntrackedOrigin"), String("MutUntrackedOrigin")]:
        var suffix = String("_ptr") if origin == "ImmUntrackedOrigin" else String("_mut_ptr")
        b.add("@staticmethod")
        b.add(
            "def "
            + tail.field_name
            + suffix
            + "(base: Pointer["
            + name
            + ", "
            + origin
            + "]) -> Pointer["
            + elem
            + ", "
            + origin
            + "]:"
        )
        b.indent()
        b.add("var raw = rebind[Pointer[" + elem + ", " + origin + "]](base)")
        b.add("return raw.unsafe_offset(" + String(tail.byte_offset) + ")")
        b.dedent()


def render_mojo_module(
    module: MojoModule, options: MojoIRPrintOptions = MojoIRPrintOptions()
) raises -> String:
    return MojoIRPrinter(options).render(module)


def _splitlines(text: String) -> List[String]:
    var lines = List[String]()
    var line = String()
    for cp in text.codepoints():
        var code = Int(cp)
        if (
            code == 10
            or code == 11
            or code == 12
            or code == 28
            or code == 29
            or code == 30
            or code == 133
            or code == 0x2028
            or code == 0x2029
        ):
            lines.append(line^)
            line = String()
        else:
            line += String(cp)
    if line:
        lines.append(line^)
    return lines^
