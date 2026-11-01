"""The libclang boundary: arguments, checked traversal, and owned source facts."""
from clang.cindex import Index, Cursor, TranslationUnit, TranslationUnitFlags, UnsavedFile
from std.pathlib import Path
from std.ffi import external_call, c_char
from ._process import command_output
from ..analysis.common import strip_whitespace
from ..ir import IRDiagnostic


struct ClangOptions(Copyable, Movable):
    var std: Optional[String]
    var target: Optional[String]
    var sysroot: Optional[String]
    var include_dirs: List[String]
    var defines: List[String]
    var undefines: List[String]
    var raw_args: List[String]

    def __init__(out self):
        self.std = None
        self.target = None
        self.sysroot = None
        self.include_dirs = List[String]()
        self.defines = List[String]()
        self.undefines = List[String]()
        self.raw_args = List[String]()

    def to_args(self) -> List[String]:
        var args: List[String] = ["-x", "c"]
        var has_std = False
        for arg in self.raw_args:
            if normalize_std_flag(arg).startswith("-std="):
                has_std = True
        if self.std:
            args.append("-std=" + self.std.value())
        elif not has_std:
            args.append("-std=gnu11")
        if self.target:
            args.append("--target=" + self.target.value())
        if self.sysroot:
            args.append("--sysroot=" + self.sysroot.value())
        for path in self.include_dirs:
            args.append("-I" + path)
        for value in self.defines:
            args.append("-D" + value)
        for value in self.undefines:
            args.append("-U" + value)
        for arg in self.raw_args:
            args.append(normalize_std_flag(arg))
        return args^


def default_system_compile_args() -> List[String]:
    var args: List[String] = ["-I/usr/include"]
    for driver in [String("cc"), String("clang")]:
        try:
            var output = strip_whitespace(command_output([driver, "-print-file-name=include"]))
            var flag = "-I" + output
            if output != "include" and output and Path(output).is_dir() and flag not in args:
                args.append(flag)
        except:
            pass
    return args^


def resolve_header(header: String) raises -> String:
    if "\0" in header:
        raise Error("NUL in header path")
    var terminated = header + "\0"
    # Linux realpath requires a PATH_MAX buffer when storage is caller-owned.
    var buffer = List[UInt8](length=4096, fill=0)
    var resolved = external_call["realpath", Optional[Pointer[c_char, MutUntrackedOrigin]]](
        terminated.unsafe_ptr(), buffer.unsafe_ptr()
    )
    if not resolved:
        raise Error("header not found: " + header)
    var path = String(unsafe_from_utf8_ptr=buffer.unsafe_ptr())
    if not Path(path).is_file():
        raise Error("header not found: " + header)
    return path^


def normalize_std_flag(arg: String) -> String:
    if arg.startswith("--std="):
        return String(arg[byte=1:])
    if arg.startswith("std="):
        return "-" + arg
    return arg.copy()


def normalized_args(args: List[String]) -> List[String]:
    var normalized = List[String]()
    var has_std = False
    var has_language = False
    for item in args:
        var arg = normalize_std_flag(item)
        has_std = has_std or arg.startswith("-std=")
        has_language = has_language or arg.startswith("-x")
        normalized.append(arg^)
    var result = List[String]()
    if not has_language:
        result.append("-x")
        result.append("c")
    if not has_std:
        result.append("-std=gnu11")
    result.extend(normalized^)
    return result^


def tokens(ref cursor: Cursor) raises -> List[String]:
    var group = cursor.tokens()
    var result = List[String]()
    for token in group:
        result.append(token.spelling())
    return result^


def children(ref cursor: Cursor) raises -> List[Cursor]:
    return cursor.children()


def walk(ref cursor: Cursor, mut result: List[Cursor]) raises:
    result.append(cursor.copy())
    for child in children(cursor):
        walk(child, result)


struct ClangFrontend(Copyable, Movable):
    var header: String
    var compile_args: List[String]
    var include_headers: List[String]

    def __init__(out self, header: String, args: List[String], headers: List[String] = []) raises:
        self.header = resolve_header(header)
        self.compile_args = normalized_args(args)
        self.include_headers = List[String]()
        for item in headers:
            var path = resolve_header(item)
            if path != self.header and path not in self.include_headers:
                self.include_headers.append(path)

    def umbrella_path(self) -> String:
        return (
            String(self.header[byte = 0 : self.header.rfind("/") + 1])
            + "__mojo_bindgen_include_headers__.h"
        )

    def umbrella_source(self) -> String:
        var source = '#include "' + c_string(self.header) + '"\n'
        for header in self.include_headers:
            source += '#include "' + c_string(header) + '"\n'
        return source^

    def parse(self) raises -> TranslationUnit:
        var index = Index.create()
        var unsaved = List[UnsavedFile]()
        var path = self.header.copy()
        if len(self.include_headers):
            path = self.umbrella_path()
            unsaved.append(UnsavedFile(path.copy(), self.umbrella_source()))
        return index.parse(
            path,
            self.compile_args,
            unsaved_files=unsaved,
            options=TranslationUnitFlags.DETAILED_PREPROCESSING_RECORD
            | TranslationUnitFlags.SKIP_FUNCTION_BODIES
            | TranslationUnitFlags.INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION,
        )


def collect_diagnostics(ref tu: TranslationUnit) raises -> List[IRDiagnostic]:
    var result = List[IRDiagnostic]()
    for diagnostic in tu.diagnostics():
        var severity = Int(diagnostic.severity().as_c_uint())
        var name = String("unknown")
        if severity == 1:
            name = "note"
        elif severity == 2:
            name = "warning"
        elif severity == 3:
            name = "error"
        elif severity == 4:
            name = "fatal"
        var loc = diagnostic.location()
        var file = loc.file_name()
        result.append(
            IRDiagnostic(
                name,
                diagnostic.spelling(),
                String(file) if file else String("<unknown>"),
                loc.line(),
                loc.column(),
            )
        )
    return result^


def c_string(text: String) -> String:
    return text.replace("\\", "\\\\").replace('"', '\\"')
