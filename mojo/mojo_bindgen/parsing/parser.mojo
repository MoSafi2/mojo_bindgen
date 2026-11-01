"""Native header-to-CIR facade; each run owns an independent parse context."""
from clang.cindex import CursorKind, Cursor
from ..ir import Unit, Decl
from .frontend import ClangFrontend, default_system_compile_args, collect_diagnostics, walk
from .registry import RecordRegistry, is_record
from .target_abi import probe_target_abi
from .lowering.const_expr import ConstExprParser
from .lowering.macro_fallback import ClangMacroFallback
from .lowering.decl_lowering import lower_decl, lower_macro


struct ClangParser(Copyable, Movable):
    var frontend: ClangFrontend
    var library: String
    var link_name: String
    var raise_on_error: Bool
    var clang_macro_fallback: Bool

    def __init__(
        out self,
        header: String,
        library: String,
        link_name: String,
        compile_args: Optional[List[String]] = {},
        raise_on_error: Bool = True,
        include_headers: List[String] = [],
        clang_macro_fallback: Bool = False,
    ) raises:
        var args = compile_args.value().copy() if compile_args else default_system_compile_args()
        self.frontend = ClangFrontend(header, args, include_headers)
        self.library = library.copy()
        self.link_name = link_name.copy()
        self.raise_on_error = raise_on_error
        self.clang_macro_fallback = clang_macro_fallback

    def run(self) raises -> Unit:
        var tu = self.frontend.parse()
        var diagnostics = collect_diagnostics(tu)
        var errors = String()
        for d in diagnostics:
            if d.severity == "error" or d.severity == "fatal":
                if errors:
                    errors += "\n"
                errors += (
                    d.file.value()
                    + ":"
                    + String(d.line.value())
                    + ":"
                    + String(d.col.value())
                    + ": "
                    + d.severity
                    + ": "
                    + d.message
                )
        if errors and self.raise_on_error:
            raise Error("libclang reported errors parsing " + self.frontend.header + ":\n" + errors)
        var root = tu.cursor()
        var registry = RecordRegistry(root)
        registry.diagnostics = diagnostics.copy()
        var parser = ConstExprParser(self.frontend.compile_args)
        var decls = List[Decl]()
        var marker = 0
        # Copy the cursor list before mutably borrowing the construction context.
        var top_level = registry.top_level.copy()
        for cursor in top_level:
            var lowered = lower_decl(registry, parser, cursor)
            if not len(lowered):
                continue
            if is_record(cursor) and cursor.is_definition() and cursor.spelling():
                while marker < len(registry.completed):
                    var key = registry.completed[marker].copy()
                    match registry.states[key]:
                        case .completed(v):
                            decls.append(Decl.struct_decl(v.copy()))
                        case _:
                            raise Error("completed record registry invariant")
                    marker += 1
            else:
                decls.extend(lowered^)
        var all_nodes = List[Cursor]()
        walk(root, all_nodes)
        var fallback = Optional[ClangMacroFallback]()
        if self.clang_macro_fallback:
            var headers: List[String] = [self.frontend.header.copy()]
            headers.extend(self.frontend.include_headers.copy())
            fallback = ClangMacroFallback(headers, self.frontend.compile_args)
        for cursor in all_nodes:
            if cursor.kind() != CursorKind.MACRO_DEFINITION or not cursor.location().file_name():
                continue
            var macro = lower_macro(parser, cursor, fallback)
            if macro:
                decls.append(Decl.macro_decl(macro.value().copy()))
        return Unit(
            self.frontend.header.copy(),
            self.library.copy(),
            self.link_name.copy(),
            probe_target_abi(self.frontend.compile_args),
            decls^,
            registry.diagnostics.copy(),
        )
