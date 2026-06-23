# Frontend services for libclang parsing.
#
# Ported from `mojo_bindgen/parsing/frontend.py`. This module owns the
# translation-unit setup boundary: path resolution, compile-argument
# normalization, translation-unit parsing, and frontend diagnostic collection.
#
# Workaround: libclang_mojo 0.1.0 has a bug in `CStringArray` that corrupts
# when 3+ args are passed to `Index.parse`. We bypass it by calling
# `clang_parseTranslationUnit2` directly with a manually-constructed C string
# array. Similarly, `TargetInfo.triple()` is buggy; we call the FFI directly.

from clang.cindex import (
    Index,
    TranslationUnit,
    TranslationUnitFlags,
    UnsavedFile,
    Cursor,
    Diagnostic,
    DiagnosticSeverity,
    CursorKind,
)
from clang._ffi import (
    clang_parseTranslationUnit2,
    CXTranslationUnit,
    clang_getTranslationUnitTargetInfo,
    clang_TargetInfo_getTriple,
    clang_TargetInfo_dispose,
    clang_TargetInfo_getPointerWidth,
    clang_getCString,
    clang_disposeString,
    CXString,
)
from clang.common import (
    _borrow_c_string,
    _alloc_c_string,
    _c_string,
    UnsavedFileArena,
)
from clang.enums import ErrorCode
from mojo.utils import build_c_parse_args, normalize_std_flag
from std.memory import alloc, UnsafePointer
from std.ffi import c_char, c_int, c_uint
from std.pathlib import Path, cwd
from std.python import Python
from std.subprocess import run


# ─────────────────────────────────────────────
# FrontendDiagnostic
# ─────────────────────────────────────────────


@fieldwise_init
struct FrontendDiagnostic(Copyable, Movable, Writable):
    """Normalized clang frontend diagnostic."""

    var severity: String
    var file: String
    var line: Int
    var col: Int
    var message: String

    def __init__(out self):
        self.severity = ""
        self.file = ""
        self.line = 0
        self.col = 0
        self.message = ""

    def write_to(self, mut writer: Some[Writer]):
        writer.write(
            self.file,
            ":",
            self.line,
            ":",
            self.col,
            ": ",
            self.severity,
            ": ",
            self.message,
        )


# ─────────────────────────────────────────────
# ClangOptions
# ─────────────────────────────────────────────


struct ClangOptions(Copyable, Movable, Writable):
    """Structured Clang argument options accepted by the public CLI."""

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

    def __init__(
        out self,
        *,
        std: Optional[String] = None,
        target: Optional[String] = None,
        sysroot: Optional[String] = None,
        var include_dirs: List[String] = List[String](),
        var defines: List[String] = List[String](),
        var undefines: List[String] = List[String](),
        var raw_args: List[String] = List[String](),
    ):
        self.std = std
        self.target = target
        self.sysroot = sysroot
        self.include_dirs = include_dirs^
        self.defines = defines^
        self.undefines = undefines^
        self.raw_args = raw_args^

    def to_args(self) raises -> List[String]:
        """Return deterministic final Clang argv for parsing."""
        var args: List[String] = ["-x", "c"]

        var normalized_raw: List[String] = []
        for arg in self.raw_args:
            normalized_raw.append(normalize_std_flag(arg))

        var has_raw_std = False
        for arg in normalized_raw:
            if arg.startswith("-std="):
                has_raw_std = True
                break

        if self.std:
            args.append("-std=" + self.std.value())
        elif not has_raw_std:
            args.append("-std=gnu11")

        if self.target:
            args.append("--target=" + self.target.value())
        if self.sysroot:
            args.append("--sysroot=" + self.sysroot.value())

        for path in self.include_dirs:
            args.append("-I" + path)
        for define in self.defines:
            args.append("-D" + define)
        for undefine in self.undefines:
            args.append("-U" + undefine)

        for arg in normalized_raw:
            args.append(arg)

        return args^


# ─────────────────────────────────────────────
# ClangFrontendConfig
# ─────────────────────────────────────────────


@fieldwise_init
struct ClangFrontendConfig(Copyable, Movable, Writable):
    """Stable parser frontend configuration for one translation unit."""

    var header: String
    var compile_args: List[String]
    var include_headers: List[String]

    def __init__(out self):
        self.header = ""
        self.compile_args = List[String]()
        self.include_headers = List[String]()


# ─────────────────────────────────────────────
# ClangFrontend
# ─────────────────────────────────────────────


struct ClangFrontend(Copyable, Movable):
    """Thin libclang translation-unit frontend wrapper."""

    var _config: ClangFrontendConfig

    def __init__(out self, var config: ClangFrontendConfig):
        self._config = config^

    def header(self) -> String:
        return self._config.header

    def include_headers(self) -> List[String]:
        return self._config.include_headers.copy()

    def configured_headers(self) -> List[String]:
        var result: List[String] = [self._config.header]
        for h in self._config.include_headers:
            result.append(h)
        return result^

    def compile_args(self) -> List[String]:
        return self._config.compile_args.copy()

    def normalized_parse_args(self) raises -> List[String]:
        """Return the exact Clang args passed to libclang."""
        return build_c_parse_args(
            self._config.compile_args, default_std="-std=gnu11"
        )

    def parse_translation_unit(self) raises -> TranslationUnit:
        """Parse the configured header into a libclang translation unit."""
        var idx = Index.create()
        var args = self.normalized_parse_args()
        var options = _translation_unit_parse_options()

        if len(self._config.include_headers) > 0:
            var umbrella_path = self._umbrella_header_path()
            var unsaved = UnsavedFile(
                filename=umbrella_path, contents=self._umbrella_header()
            )
            var unsaved_files: List[UnsavedFile] = [unsaved^]
            return _parse_translation_unit_direct(
                idx, umbrella_path, args, unsaved_files, options
            )

        return _parse_translation_unit_direct(
            idx, self._config.header, args, List[UnsavedFile](), options
        )

    def dump_preprocessed(self) raises -> String:
        """Return preprocessed source for the configured header."""
        var args = self.normalized_parse_args()
        if len(self._config.include_headers) > 0:
            var input_path = self._umbrella_header_path()
            var source = self._umbrella_header()
            var cmd = "clang -E " + _join_args(args) + " -"
            # Use Python subprocess for stdin piping
            var py = Python()
            var subprocess = Python.import_module("subprocess")
            var proc = subprocess.run(
                cmd.split(), input=source, capture_output=True, text=True
            )
            if not Python.is_true(proc.returncode == 0):
                var stderr_str = String(py.as_string_slice(proc.stderr))
                raise Error(
                    "clang preprocessing failed for "
                    + input_path
                    + " with args "
                    + _join_args(args)
                    + ":\n"
                    + stderr_str
                )
            return String(py.as_string_slice(proc.stdout))
        else:
            var input_path = self._config.header
            var cmd = "clang -E " + _join_args(args) + " " + input_path
            var py = Python()
            var subprocess = Python.import_module("subprocess")
            var proc = subprocess.run(
                cmd.split(), capture_output=True, text=True
            )
            if not Python.is_true(proc.returncode == 0):
                var stderr_str = String(py.as_string_slice(proc.stderr))
                raise Error(
                    "clang preprocessing failed for "
                    + input_path
                    + " with args "
                    + _join_args(args)
                    + ":\n"
                    + stderr_str
                )
            return String(py.as_string_slice(proc.stdout))

    def collect_diagnostics(
        self, tu: TranslationUnit
    ) raises -> List[FrontendDiagnostic]:
        """Normalize libclang diagnostics into plain data."""
        var out: List[FrontendDiagnostic] = []
        var diags = tu.diagnostics()
        for i in range(len(diags)):
            var d = diags[i]
            var severity = _severity_string(d.severity())
            var loc = d.location()
            var file_name = "<unknown>"
            var line = 0
            var col = 0
            var file_opt = loc.file()
            if file_opt:
                file_name = file_opt.value().name()
            line = loc.line()
            col = loc.column()
            var diag = FrontendDiagnostic()
            diag.severity = severity
            diag.file = file_name
            diag.line = line
            diag.col = col
            diag.message = d.spelling()
            out.append(diag^)
        return out^

    def iter_translation_unit_cursors(
        self, tu: TranslationUnit
    ) raises -> List[Cursor]:
        """Return top-level translation-unit cursors in source order."""
        return tu.cursor().children()

    def _umbrella_header_path(self) -> String:
        """Return a stable virtual header path for multi-header parsing."""
        var p = Path(self._config.header)
        return String(p.parent()) + "/__mojo_bindgen_include_headers__.h"

    def _umbrella_header(self) -> String:
        var lines: List[String] = []
        for h in self.configured_headers():
            lines.append('#include "' + _escape_include_path(h) + '"')
        return _join_strings(lines, "\n") + "\n"


# ─────────────────────────────────────────────
# Free-function helpers
# ─────────────────────────────────────────────


def _resolve_header_path(header: String) raises -> String:
    """Resolve a header path relative to the current working directory."""
    var py = Python()
    var os_path = Python.import_module("os.path")

    var is_abs = os_path.isabs(header)
    var full_path = header
    if not Python.is_true(is_abs):
        full_path = String(cwd()) + "/" + header

    var real = os_path.realpath(full_path)
    var resolved_str = String(py.as_string_slice(real))

    var isfile = os_path.isfile(resolved_str)
    if not Python.is_true(isfile):
        raise Error("header not found: " + header)
    return resolved_str


def _probe_compiler_include(driver: String) -> Optional[String]:
    """Return an extra -I include directory from a compiler driver."""
    try:
        var out = run(driver + " -print-file-name=include")
        if out != "include" and out != "":
            var p = Path(out)
            if p.is_dir():
                return Optional[String](out)
        return None
    except:
        return None


def _default_system_compile_args() raises -> List[String]:
    """Return default include flags for libclang parsing."""
    var args: List[String] = ["-I/usr/include"]
    var seen: List[String] = ["-I/usr/include"]

    for driver in ["cc", "clang"]:
        var inc = _probe_compiler_include(driver)
        if inc:
            var flag = "-I" + inc.value()
            var already_seen = False
            for s in seen:
                if s == flag:
                    already_seen = True
                    break
            if not already_seen:
                args.append(flag)
                seen.append(flag)

    if len(args) == 1:
        print(
            "Warning: Could not probe a system include directory via cc or"
            " clang (using -I/usr/include only). If standard headers fail to"
            " resolve, pass explicit -I/--sysroot flags in compile_args."
        )

    return args^


def _escape_include_path(header: String) -> String:
    """Escape a header path for a C quoted include directive."""
    var result = header.replace("\\", "\\\\")
    result = result.replace('"', '\\"')
    return result


def _translation_unit_parse_options() -> TranslationUnitFlags:
    """Return parse option flags matching the Python frontend."""
    var options = (
        TranslationUnitFlags.DETAILED_PREPROCESSING_RECORD
        | TranslationUnitFlags.SKIP_FUNCTION_BODIES
    )
    # INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION may not exist in all bindings
    try:
        options = (
            options
            | TranslationUnitFlags.INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION
        )
    except:
        pass
    return options


def _severity_string(sev: DiagnosticSeverity) -> String:
    if sev == DiagnosticSeverity.NOTE:
        return "note"
    if sev == DiagnosticSeverity.WARNING:
        return "warning"
    if sev == DiagnosticSeverity.ERROR:
        return "error"
    if sev == DiagnosticSeverity.FATAL:
        return "fatal"
    return "unknown"


def _join_args(args: List[String]) -> String:
    """Join args into a space-separated string for subprocess commands."""
    var result = ""
    var first = True
    for arg in args:
        if not first:
            result += " "
        result += arg
        first = False
    return result


def _join_strings(strings: List[String], separator: String) -> String:
    var result = ""
    var first = True
    for s in strings:
        if not first:
            result += separator
        result += s
        first = False
    return result


# ─────────────────────────────────────────────
# Direct FFI parse workaround
# ─────────────────────────────────────────────


def _parse_translation_unit_direct(
    ref index: Index,
    path: String,
    args: List[String],
    unsaved_files: List[UnsavedFile],
    options: TranslationUnitFlags,
) raises -> TranslationUnit:
    """Parse a translation unit, working around the CStringArray bug.

    libclang_mojo 0.1.0's CStringArray corrupts when 3+ args are passed.
    We build the C string array manually and call clang_parseTranslationUnit2
    directly.
    """
    var n = len(args)
    var cstrs: List[UnsafePointer[c_char, MutAnyOrigin]] = []

    comptime SlotType = Optional[UnsafePointer[c_char, ImmutUntrackedOrigin]]
    var slots_opt: Optional[
        UnsafePointer[SlotType, ImmutUntrackedOrigin]
    ] = None
    var slots_mut_opt: Optional[UnsafePointer[SlotType, MutAnyOrigin]] = None

    if n > 0:
        var slots = alloc[SlotType](n)
        slots_mut_opt = Optional[UnsafePointer[SlotType, MutAnyOrigin]](slots)
        for i in range(n):
            var s = _alloc_c_string(args[i])
            cstrs.append(s)
            slots[i] = SlotType(_c_string(s))
        slots_opt = Optional[UnsafePointer[SlotType, ImmutUntrackedOrigin]](
            rebind[UnsafePointer[SlotType, ImmutUntrackedOrigin]](slots)
        )

    var unsaved_arena = UnsavedFileArena(unsaved_files)

    var out_tu: CXTranslationUnit = CXTranslationUnit()
    var out_ptr = UnsafePointer[CXTranslationUnit, MutAnyOrigin](to=out_tu)

    var raw_err = clang_parseTranslationUnit2(
        index._raw_handle(),
        _borrow_c_string(path),
        slots_opt,
        c_int(n),
        unsaved_arena.ptr(),
        unsaved_arena.count(),
        options.as_c_uint(),
        rebind[UnsafePointer[CXTranslationUnit, MutUntrackedOrigin]](out_ptr),
    )

    for s in cstrs:
        s.free()
    if slots_mut_opt:
        slots_mut_opt.value().free()

    var err = ErrorCode(raw_err)
    if err != ErrorCode.SUCCESS:
        raise Error("parse failed: error code=" + String(Int(err.as_c_uint())))

    return TranslationUnit(index._shared_state(), out_tu)


def _get_target_triple(tu: TranslationUnit) raises -> String:
    """Get the target triple via direct FFI (workaround for buggy TargetInfo.triple()).
    """
    var ti = clang_getTranslationUnitTargetInfo(tu._raw_handle())
    if not ti:
        raise Error("null target info")

    var cs_ptr = alloc[CXString](1)
    cs_ptr[] = CXString(data=None, private_flags=c_uint(0))

    clang_TargetInfo_getTriple(
        Optional[UnsafePointer[CXString, MutUntrackedOrigin]](cs_ptr),
        ti,
    )

    var c_str = clang_getCString(cs_ptr)
    var result = String("")
    if c_str:
        result = String(unsafe_from_utf8_ptr=c_str.value())

    clang_disposeString(cs_ptr)
    cs_ptr.free()
    clang_TargetInfo_dispose(ti)
    return result


def _get_target_pointer_width(tu: TranslationUnit) raises -> Int:
    """Get the target pointer width in bits via direct FFI."""
    var ti = clang_getTranslationUnitTargetInfo(tu._raw_handle())
    if not ti:
        raise Error("null target info")
    var w = Int(clang_TargetInfo_getPointerWidth(ti))
    clang_TargetInfo_dispose(ti)
    return w
