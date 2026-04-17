"""Frontend services for libclang parsing.

This module owns the translation-unit setup boundary for the parser package:
path resolution, compile-argument normalization, primary-file filtering, and
frontend diagnostic collection.
"""

from __future__ import annotations

import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Iterator

import clang.cindex as cx

from mojo_bindgen.utils import build_c_parse_args


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
class ClangFrontendConfig:
    """Stable parser frontend configuration for one translation unit."""

    header: Path
    compile_args: tuple[str, ...]


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
    def compile_args(self) -> tuple[str, ...]:
        return self.config.compile_args

    def parse_translation_unit(self) -> cx.TranslationUnit:
        """Parse the configured header into a libclang translation unit."""
        index = cx.Index.create()
        args = build_c_parse_args(list(self.compile_args), default_std="-std=gnu11")
        return index.parse(
            str(self.header),
            args=args,
            options=(
                cx.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
                | cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
            ),
        )

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

    def is_primary_file_cursor(self, cursor: cx.Cursor) -> bool:
        """Return whether a cursor originates from the configured header."""
        loc = cursor.location
        return bool(loc.file and Path(loc.file.name).resolve() == self.header)

    def iter_primary_cursors(self, tu: cx.TranslationUnit) -> Iterator[cx.Cursor]:
        """Yield top-level cursors from the primary file in source order."""
        for cursor in tu.cursor.get_children():
            if self.is_primary_file_cursor(cursor):
                yield cursor


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
        if not callable(getter):
            return None
        try:
            count = getter()
        except Exception:
            return None
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
