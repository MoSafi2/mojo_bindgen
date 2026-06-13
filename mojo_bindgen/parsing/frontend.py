"""Frontend services for libclang parsing.

This module owns the translation-unit setup boundary for the parser package:
path resolution, compile-argument normalization, translation-unit parsing, and
frontend diagnostic collection.
"""

from __future__ import annotations

import subprocess
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

import clang.cindex as cx

from mojo_bindgen.utils import build_c_parse_args, normalize_std_flag


@dataclass(frozen=True)
class FrontendDiagnostic:
    """Normalized clang frontend diagnostic."""

    severity: str
    file: str
    line: int
    col: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.col}: {self.severity}: {self.message}"


@dataclass(frozen=True)
class ClangOptions:
    """Structured Clang argument options accepted by the public CLI."""

    std: str | None = None
    target: str | None = None
    sysroot: Path | None = None
    include_dirs: tuple[Path, ...] = ()
    defines: tuple[str, ...] = ()
    undefines: tuple[str, ...] = ()
    raw_args: tuple[str, ...] = ()

    def to_args(self) -> list[str]:
        """Return deterministic final Clang argv for parsing."""
        args = ["-x", "c"]
        raw_args = [normalize_std_flag(arg) for arg in self.raw_args]
        has_raw_std = any(arg.startswith("-std=") for arg in raw_args)
        if self.std is not None:
            args.append(f"-std={self.std}")
        elif not has_raw_std:
            args.append("-std=gnu11")
        if self.target is not None:
            args.append(f"--target={self.target}")
        if self.sysroot is not None:
            args.append(f"--sysroot={self.sysroot}")
        args.extend(f"-I{path}" for path in self.include_dirs)
        args.extend(f"-D{define}" for define in self.defines)
        args.extend(f"-U{undefine}" for undefine in self.undefines)
        args.extend(raw_args)
        return args


@dataclass(frozen=True)
class ClangFrontendConfig:
    """Stable parser frontend configuration for one translation unit."""

    header: Path
    compile_args: tuple[str, ...]
    include_headers: tuple[Path, ...] = ()


_SEVERITY = {
    cx.Diagnostic.Note: "note",
    cx.Diagnostic.Warning: "warning",
    cx.Diagnostic.Error: "error",
    cx.Diagnostic.Fatal: "fatal",
}


def _resolve_header_path(header: Path | str) -> Path:
    """Resolve a header path relative to the current working directory."""
    p = Path(header)
    resolved = (p if p.is_absolute() else Path.cwd() / p).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"header not found: {header!r}")
    return resolved


def _probe_compiler_include(driver: str) -> str | None:
    """Return an extra ``-I`` include directory from a compiler driver."""
    try:
        out = subprocess.check_output(
            [driver, "-print-file-name=include"], text=True, timeout=10
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if out and out != "include" and Path(out).is_dir():
        return out
    return None


# Make the compiler include parametric, using gcc, cc, and clang as probes, allow multiple values.
def _default_system_compile_args() -> list[str]:
    """Return default include flags for libclang parsing."""
    args = ["-I/usr/include"]
    seen: set[str] = {"-I/usr/include"}
    for driver in ("cc", "clang"):
        inc = _probe_compiler_include(driver)
        if inc:
            flag = f"-I{inc}"
            if flag not in seen:
                args.append(flag)
                seen.add(flag)
    if len(args) == 1:
        warnings.warn(
            "Could not probe a system include directory via cc or clang "
            "(using -I/usr/include only). If standard headers fail to resolve, "
            "pass explicit -I/--sysroot flags in compile_args.",
            UserWarning,
            stacklevel=2,
        )
    return args


class ClangFrontend:
    """Thin libclang translation-unit frontend wrapper."""

    def __init__(self, config: ClangFrontendConfig) -> None:
        self.config = config

    @property
    def header(self) -> Path:
        return self.config.header

    @property
    def include_headers(self) -> tuple[Path, ...]:
        return self.config.include_headers

    @property
    def configured_headers(self) -> tuple[Path, ...]:
        return (self.header, *self.include_headers)

    @property
    def compile_args(self) -> tuple[str, ...]:
        return self.config.compile_args

    def normalized_parse_args(self) -> list[str]:
        """Return the exact Clang args passed to libclang."""
        return build_c_parse_args(list(self.compile_args), default_std="-std=gnu11")

    def parse_translation_unit(self) -> cx.TranslationUnit:
        """Parse the configured header into a libclang translation unit."""
        index = cx.Index.create()
        args = self.normalized_parse_args()
        options = _translation_unit_parse_options()
        if self.include_headers:
            umbrella_path = self._umbrella_header_path()
            return index.parse(
                str(umbrella_path),
                args=args,
                unsaved_files=[(str(umbrella_path), self._umbrella_header())],
                options=options,
            )
        return index.parse(
            str(self.header),
            args=args,
            options=options,
        )

    def dump_preprocessed(self) -> str:
        """Return preprocessed source for the configured primary or umbrella header."""
        if self.include_headers:
            input_path = self._umbrella_header_path()
            cmd = ["clang", "-E", *self.normalized_parse_args(), "-"]
            source = self._umbrella_header()
            proc = subprocess.run(
                cmd,
                input=source,
                text=True,
                capture_output=True,
                check=False,
            )
        else:
            input_path = self.header
            cmd = ["clang", "-E", *self.normalized_parse_args(), str(input_path)]
            proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            raise RuntimeError(
                "clang preprocessing failed for "
                f"{input_path} with args {self.normalized_parse_args()}:\n{proc.stderr}"
            )
        return proc.stdout

    def collect_diagnostics(self, tu: cx.TranslationUnit) -> list[FrontendDiagnostic]:
        """Normalize libclang diagnostics into plain dataclasses."""
        out: list[FrontendDiagnostic] = []
        for d in tu.diagnostics:
            sev = _SEVERITY.get(d.severity, "unknown")
            loc = d.location
            out.append(
                FrontendDiagnostic(
                    severity=sev,
                    file=loc.file.name if loc.file else "<unknown>",
                    line=loc.line,
                    col=loc.column,
                    message=d.spelling,
                )
            )
        return out

    def iter_translation_unit_cursors(self, tu: cx.TranslationUnit) -> Iterator[cx.Cursor]:
        """Yield top-level translation-unit cursors in source order."""
        yield from tu.cursor.get_children()

    def _umbrella_header_path(self) -> Path:
        """Return a stable virtual header path used for multi-header parsing."""
        return self.header.parent / "__mojo_bindgen_include_headers__.h"

    def _umbrella_header(self) -> str:
        includes = "\n".join(
            f'#include "{_escape_include_path(header)}"' for header in self.configured_headers
        )
        return f"{includes}\n"


def _escape_include_path(header: Path) -> str:
    """Escape a header path for a C quoted include directive."""
    return str(header).replace("\\", "\\\\").replace('"', '\\"')


def _translation_unit_parse_options() -> int:
    options = (
        cx.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
        | cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
    )
    include_brief_comments = getattr(
        cx.TranslationUnit,
        "PARSE_INCLUDE_BRIEF_COMMENTS_IN_CODE_COMPLETION",
        0,
    )
    return options | include_brief_comments


@dataclass
class ClangCompat:
    """Compatibility helpers for libclang Python binding differences."""

    _value_type_api_ready: ClassVar[bool | None] = None

    def get_calling_convention(self, t: cx.Type) -> str | None:
        """Return a readable calling-convention string if available."""
        if hasattr(t, "get_canonical"):
            t = t.get_canonical()
        getter = getattr(t, "get_calling_conv", None)
        if getter is None:
            getter = getattr(t, "calling_conv", None)
        if getter is None:
            return None
        try:
            value = getter() if callable(getter) else getter
        except Exception:
            return None
        if value is None:
            return None
        name = getattr(value, "name", None)
        if isinstance(name, str) and name:
            return name
        try:
            return str(value)
        except Exception:
            return None

    def get_element_type(self, t: cx.Type) -> cx.Type:
        """Return a vector or complex element type across libclang variants."""
        getter = getattr(t, "get_element_type", None)
        if callable(getter):
            return getter()
        return getattr(t, "element_type")

    def get_num_elements(self, t: cx.Type) -> int | None:
        """Return vector element count across libclang variants."""
        getter = getattr(t, "get_num_elements", None)
        if callable(getter):
            try:
                count = getter()
            except Exception:
                count = None
            if isinstance(count, int) and count >= 0:
                return count
        count = getattr(t, "element_count", None)
        return count if isinstance(count, int) and count >= 0 else None

    @classmethod
    def _ensure_value_type_api(cls) -> bool:
        """Register ``clang_Type_getValueType`` when libclang exposes it."""
        if cls._value_type_api_ready is not None:
            return cls._value_type_api_ready
        try:
            cx.register_function(
                cx.conf.lib,
                ("clang_Type_getValueType", [cx.Type], cx.Type, cx.Type.from_result),
                False,
            )
        except Exception:
            cls._value_type_api_ready = False
        else:
            cls._value_type_api_ready = True
        return cls._value_type_api_ready

    def get_value_type(self, t: cx.Type) -> cx.Type | None:
        """Return the modified value type for wrappers like ``_Atomic(T)``."""
        getter = getattr(t, "get_value_type", None)
        if callable(getter):
            try:
                value_type = getter()
            except Exception:
                return None
            return None if value_type.kind == cx.TypeKind.INVALID else value_type
        if not self._ensure_value_type_api():
            return None
        try:
            value_type = cx.conf.lib.clang_Type_getValueType(t)
        except Exception:
            return None
        return None if value_type.kind == cx.TypeKind.INVALID else value_type
