# mojo_bindgen/parser.py
"""
ClangParser — walks a clang TranslationUnit and produces a Unit.

Responsibilities:
  - Parse the header with libclang, applying caller-supplied compile flags
  - Walk top-level cursors that originate from the primary file
  - Convert every supported C construct to the corresponding IR node
  - Resolve typedef chains and detect opaque (incomplete) types
  - Extract plain integer/hex #define macros as Const nodes
  - Collect diagnostics and surface fatal parse errors

NOT responsible for:
  - Name remapping  (NameMapper pass)
  - Allow/deny filtering  (AllowlistFilter pass)
  - Cross-referencing typedefs with struct declarations (TypeResolver pass)
"""

from __future__ import annotations

import os
import re
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import clang.cindex as cx

from mojo_bindgen.utils import build_c_parse_args
from mojo_bindgen.ir import (
    Const,
    Decl,
    Enum,
    Enumerant,
    Function,
    IRDiagnostic,
    Param,
    Primitive,
    PrimitiveKind,
    Struct,
    Typedef,
    Unit,
)
from mojo_bindgen.parsing.struct_builder import StructBuilder
from mojo_bindgen.parsing.type_builder import TypeBuilder, TypeContext
from mojo_bindgen.parsing.type_resolver import TypeResolver


# ─────────────────────────────────────────────────────────────────────────────
#  Diagnostic helpers
# ─────────────────────────────────────────────────────────────────────────────

class ParseError(RuntimeError):
    """Raised when libclang reports fatal errors in the translation unit."""


@dataclass
class FrontendDiagnostic:
    severity: str   # "note" | "warning" | "error" | "fatal"
    file: str
    line: int
    col: int
    message: str

    def __str__(self) -> str:
        # GCC/clang-style: file:line:col: severity: message
        return f"{self.file}:{self.line}:{self.col}: {self.severity}: {self.message}"


_SEVERITY = {
    cx.Diagnostic.Note:    "note",
    cx.Diagnostic.Warning: "warning",
    cx.Diagnostic.Error:   "error",
    cx.Diagnostic.Fatal:   "fatal",
}

# Regex for integer/hex literals: optional sign (no space before digits), optional suffix
_INT_LITERAL_RE = re.compile(
    r"^([+-]?)"
    r"(0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)"
    r"([uUlL]*)$",
)


def _match_int_literal(raw: str) -> tuple[int | None, str]:
    """
    Parse a single integer literal token (same rules as #define macro literals).
    Returns (value, suffix) or (None, "").
    """
    m = _INT_LITERAL_RE.match(raw.strip())
    if not m:
        return None, ""
    sign = m.group(1) or ""
    num_str = m.group(2)
    suf = m.group(3) or ""
    try:
        value = int(num_str, 0)
    except ValueError:
        return None, ""
    if sign == "-":
        value = -value
    return value, suf


def _resolve_header_path(header: Path | str) -> Path:
    """Resolve a header path to an existing file, relative to cwd."""
    p = Path(header)
    resolved = (p if p.is_absolute() else Path.cwd() / p).resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"header not found: {header!r}")
    return resolved


def _probe_compiler_include(driver: str) -> str | None:
    """Return an extra ``-I`` path from ``driver -print-file-name=include``, or None."""
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
    """
    Include paths so system headers (<stddef.h>, <stdint.h>, …) resolve.

    libclang's ``parse`` call does not always inherit the full compiler-driver
    include path set.  We always add ``-I/usr/include``, then try
    ``cc -print-file-name=include`` and ``clang -print-file-name=include`` (in
    that order) for an additional ``-I`` when the probe returns a directory.

    If neither driver is available or both probes fail, a :exc:`UserWarning`
    is emitted once so callers know they may need explicit ``-I`` / ``--sysroot``
    in ``compile_args`` (e.g. NixOS, cross-compilers).
    """
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


# ─────────────────────────────────────────────────────────────────────────────
#  ClangParser
# ─────────────────────────────────────────────────────────────────────────────

class ClangParser:
    """
    Parse one C header and produce a Unit.

    Construction only resolves paths and stores options; libclang parsing and
    :exc:`ParseError` happen in :meth:`run`.

    Parameters
    ----------
    header:
        Path to the ``.h`` file. Absolute paths must exist. Relative paths are
        resolved against the **current working directory**; installed
        packages should pass absolute paths or set cwd appropriately.
    library:
        Logical library name written into Unit (e.g. ``"zlib"``).
    link_name:
        Shared-library link name written into Unit (e.g. ``"z"``).
    compile_args:
        Flags forwarded to libclang **in addition** to ``-x c -std=gnu11`` (and
        the primary file). If ``None`` (default), :func:`_default_system_compile_args`
        supplies typical ``-I`` paths (``/usr/include`` plus a probe from ``cc`` /
        ``clang``). For cross-compilation, NixOS, or non-default sysroots, pass
        explicit ``-I``, ``-isystem``, ``--sysroot``, and target triple flags
        here so ``#include <stdint.h>`` and system headers resolve. Pass ``[]``
        to disable the default system includes (only the bare parse flags apply).
        C standard flags are accepted as ``-std=...``, ``--std=...``, or
        ``std=...`` and normalized to ``-std=...``.
    raise_on_error:
        If True (default), raise ParseError when clang reports error/fatal
        diagnostics. Set to False to collect partial results despite errors.
    """

    def __init__(
        self,
        header: Path | str,
        library: str,
        link_name: str,
        compile_args: list[str] | None = None,
        raise_on_error: bool = True,
    ) -> None:
        self.header = _resolve_header_path(header)
        self.library = library
        self.link_name = link_name
        self.compile_args = (
            _default_system_compile_args()
            if compile_args is None
            else list(compile_args)
        )
        self.raise_on_error = raise_on_error

        # diagnostics collected during the run
        self.diagnostics: list[FrontendDiagnostic] = []

        # Unit accumulator
        self._decls: list[Decl] = []

        self._tu: cx.TranslationUnit | None = None

        self._resolver = TypeResolver(
            compile_args=self.compile_args,
            append_type_kind_warning=self._append_type_kind_warning,
            build_struct=self._build_struct,
        )
        self._type_builder = TypeBuilder(self._resolver)

    def _append_diag(self, severity: str, cursor: cx.Cursor, message: str) -> None:
        loc = cursor.location
        self.diagnostics.append(
            FrontendDiagnostic(
                severity=severity,
                file=loc.file.name if loc.file else "<unknown>",
                line=loc.line,
                col=loc.column,
                message=message,
            )
        )

    def _append_type_kind_warning(self, clang_type: cx.Type, kind_label: str) -> None:
        self.diagnostics.append(
            FrontendDiagnostic(
                severity="warning",
                file="<type>",
                line=0,
                col=0,
                message=f"{kind_label}: {clang_type.spelling!r}",
            )
        )

    @staticmethod
    def _decl_id(cursor: cx.Cursor) -> str:
        usr = cursor.get_usr()
        if usr:
            return usr
        loc = cursor.location
        return f"{loc.file}:{loc.line}:{loc.column}:{cursor.kind}:{cursor.spelling}"

    # ── public entry point ────────────────────────────────────────────────────

    def run(self) -> Unit:
        """
        Parse the header (if not already done), walk the translation unit, and
        return the populated Unit. Call once per ClangParser instance.

        Pass 1 — struct/union registry: record defined tag names for opaque vs
        complete resolution.

        Pass 2 — AST to IR: top-level cursors from the primary file in order.

        Pass 3 — macros: simple integer ``#define`` constants appended after AST decls.
        """
        if self._tu is None:
            self._tu = self._parse()

        assert self._tu is not None

        # Pass 1: collect all struct/union definitions so we know which names are
        # opaque vs fully defined before we process any fields.
        self._collect_defined_structs(self._tu.cursor)

        # Pass 2: emit IR declarations in source order.
        for cursor in self._primary_cursors():
            decl = self._visit_top_level(cursor)
            if decl is None:
                continue
            if isinstance(decl, list):
                self._decls.extend(decl)
            else:
                self._decls.append(decl)

        # Pass 3: extract integer #define macros (after AST decls).
        self._decls.extend(self._collect_macros())

        return Unit(
            source_header=str(self.header),
            library=self.library,
            link_name=self.link_name,
            decls=self._decls,
            diagnostics=[
                IRDiagnostic(
                    severity=d.severity,
                    message=d.message,
                    file=d.file,
                    line=d.line,
                    col=d.col,
                )
                for d in self.diagnostics
            ],
        )

    # ── parsing ───────────────────────────────────────────────────────────────

    def _parse(self) -> cx.TranslationUnit:
        index = cx.Index.create()
        args = build_c_parse_args(self.compile_args, default_std="-std=gnu11")
        tu = index.parse(
            str(self.header),
            args=args,
            options=(
                cx.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
                | cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
            ),
        )
        # Collect and optionally raise on diagnostics.
        for d in tu.diagnostics:
            sev = _SEVERITY.get(d.severity, "unknown")
            loc = d.location
            diag = FrontendDiagnostic(
                severity=sev,
                file=loc.file.name if loc.file else "<unknown>",
                line=loc.line,
                col=loc.column,
                message=d.spelling,
            )
            self.diagnostics.append(diag)

        fatal = [d for d in self.diagnostics if d.severity in ("error", "fatal")]
        if fatal and self.raise_on_error:
            msg = "\n".join(str(d) for d in fatal)
            raise ParseError(f"libclang reported errors parsing {self.header}:\n{msg}")

        return tu

    # ── cursor iteration ──────────────────────────────────────────────────────

    def _primary_cursors(self) -> Iterator[cx.Cursor]:
        """Yield top-level cursors from the primary file only."""
        assert self._tu is not None
        for cursor in self._tu.cursor.get_children():
            loc = cursor.location
            if loc.file and Path(loc.file.name).resolve() == self.header:
                yield cursor

    def _collect_defined_structs(self, root: cx.Cursor) -> None:
        """
        Walk the TU and record struct/union definitions that appear in the
        primary file so forward references can be distinguished from opaque
        incomplete types.  System headers are skipped.
        """
        for cursor in root.walk_preorder():
            if cursor.kind not in (
                cx.CursorKind.STRUCT_DECL,
                cx.CursorKind.UNION_DECL,
            ) or not cursor.is_definition():
                continue
            loc = cursor.location
            if not loc.file or Path(loc.file.name).resolve() != self.header:
                continue
            if cursor.spelling:
                self._resolver.defined_structs.add(cursor.spelling)

    # ── top-level dispatch ────────────────────────────────────────────────────

    def _visit_top_level(self, cursor: cx.Cursor) -> Decl | list[Const] | None:
        """
        Dispatch a top-level cursor to the appropriate builder.
        Returns None for unsupported / already-handled constructs.
        """
        k = cursor.kind

        if k == cx.CursorKind.FUNCTION_DECL:
            return self._build_function(cursor)

        if k in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL):
            # Only emit if the cursor IS the definition; forward declarations
            # are picked up lazily when they appear as field/param types.
            if cursor.is_definition() and cursor.spelling:
                nested: list[Struct] = []
                s = self._build_struct(cursor, nested)
                if s is None:
                    return None
                if nested:
                    return nested + [s]
                return s
            return None

        if k == cx.CursorKind.ENUM_DECL:
            if not cursor.is_definition():
                return None
            # Anonymous enums lower to top-level Const nodes (policy lives here).
            if not cursor.spelling:
                return self._anonymous_enum_as_consts(cursor)
            return self._build_enum(cursor)

        if k == cx.CursorKind.TYPEDEF_DECL:
            return self._build_typedef(cursor)

        if k == cx.CursorKind.VAR_DECL:
            # Top-level const variables (rare in C headers but legal)
            return self._build_var_const(cursor)

        # Everything else (includes, macro expansions, class templates …)
        # is silently ignored at the top level.
        return None

    # ── function ──────────────────────────────────────────────────────────────

    def _build_function(self, cursor: cx.Cursor) -> Function | None:
        """
        FUNCTION_DECL cursor → Function.

        We do NOT emit function bodies here — PARSE_SKIP_FUNCTION_BODIES
        ensures clang never gives us one.  The cursor's type contains the
        full prototype even for K&R-style declarations.
        """
        fn_type = cursor.type  # FunctionProto or FunctionNoProto

        # Return type
        ret_ir = self._type_builder.build(fn_type.get_result(), TypeContext.RETURN)

        # Parameters — iterate child cursors of kind PARM_DECL
        params: list[Param] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PARM_DECL:
                param_type = self._type_builder.build(child.type, TypeContext.PARAM)
                params.append(Param(name=child.spelling, type=param_type))

        is_variadic = (
            fn_type.kind == cx.TypeKind.FUNCTIONPROTO
            and fn_type.is_function_variadic()
        )
        if fn_type.kind == cx.TypeKind.FUNCTIONNOPROTO:
            self._append_diag(
                "warning",
                cursor,
                "function has no prototype (K&R-style); parameters may be incomplete",
            )

        return Function(
            decl_id=self._decl_id(cursor),
            name=cursor.spelling,
            link_name=cursor.spelling,
            ret=ret_ir,
            params=params,
            is_variadic=is_variadic,
            calling_convention=self._type_builder._calling_convention(fn_type),
        )

    # ── struct / union ────────────────────────────────────────────────────────
    def _build_struct(
        self, cursor: cx.Cursor, nested_out: list[Struct] | None
    ) -> Struct | None:
        """
        STRUCT_DECL or UNION_DECL cursor (definition) → Struct.

        Layout comes from clang. Bitfield members use :class:`Field` metadata;
        ``nested_out`` collects anonymous nested struct/union bodies (field
        order) so the caller can emit them before the parent.
        """
        result = StructBuilder(
            cursor=cursor,
            resolver=self._resolver,
            build_struct_cb=self._build_struct,
        ).build()
        struct = result.struct
        self._resolver.type_cache[cursor.get_usr()] = struct
        if nested_out is not None:
            nested_out.extend(result.nested)
            if not cursor.spelling:
                nested_out.append(struct)
        return struct

    # ── enum ──────────────────────────────────────────────────────────────────

    def _anonymous_enum_as_consts(self, cursor: cx.Cursor) -> list[Const]:
        """
        Anonymous ENUM_DECL (definition): emit each enumerant as a top-level Const.
        """
        underlying_clang = cursor.enum_type
        underlying = self._resolver.resolve_primitive(underlying_clang)
        if underlying is None:
            underlying = Primitive(
                "int",
                kind=PrimitiveKind.INT,
                is_signed=True,
                size_bytes=4,
            )
        out: list[Const] = []
        for child in cursor.get_children():
            if child.kind != cx.CursorKind.ENUM_CONSTANT_DECL:
                continue
            out.append(
                Const(
                    name=child.spelling,
                    type=underlying,
                    value=child.enum_value,
                )
            )
        return out

    def _build_enum(self, cursor: cx.Cursor) -> Enum | None:
        """
        Named ENUM_DECL cursor (definition) → Enum.

        Call only when ``cursor.spelling`` is non-empty; anonymous enums use
        :meth:`_anonymous_enum_as_consts`.

        The underlying integer type comes from clang's ``enum_type`` on the
        cursor (new enough libclang) or falls back to a fixed int.
        """
        c_name = cursor.spelling
        if not c_name:
            return None
        underlying_clang = cursor.enum_type
        underlying = self._resolver.resolve_primitive(underlying_clang)
        if underlying is None:
            underlying = Primitive(
                "int",
                kind=PrimitiveKind.INT,
                is_signed=True,
                size_bytes=4,
            )

        enumerants: list[Enumerant] = []
        for child in cursor.get_children():
            if child.kind != cx.CursorKind.ENUM_CONSTANT_DECL:
                continue
            enumerants.append(Enumerant(
                name=child.spelling,
                c_name=child.spelling,
                value=child.enum_value,
            ))

        return Enum(
            decl_id=self._decl_id(cursor),
            name=c_name,
            c_name=c_name,
            underlying=underlying,
            enumerants=enumerants,
        )

    # ── typedef ───────────────────────────────────────────────────────────────

    def _build_typedef(self, cursor: cx.Cursor) -> Typedef | None:
        """
        TYPEDEF_DECL cursor → Typedef.

        ``aliased`` is the direct underlying clang type (one typedef step), often
        a :class:`~mojo_bindgen.ir.TypeRef`.  ``canonical`` is the fully
        unrolled type for ABI lowering.
        """
        name = cursor.spelling
        ut = cursor.underlying_typedef_type
        aliased = self._type_builder.build(ut, TypeContext.TYPEDEF)
        canonical = self._type_builder.build(ut.get_canonical(), TypeContext.TYPEDEF)
        return Typedef(
            decl_id=self._decl_id(cursor),
            name=name,
            aliased=aliased,
            canonical=canonical,
        )

    # ── top-level const variable ───────────────────────────────────────────────

    def _build_var_const(self, cursor: cx.Cursor) -> Const | None:
        """
        Top-level VAR_DECL with a constant initialiser → Const.
        Only integer types are supported; anything else is skipped.
        """
        if cursor.type.is_const_qualified():
            prim = self._resolver.resolve_primitive(cursor.type)
            if prim is not None and prim.kind not in (
                PrimitiveKind.FLOAT,
                PrimitiveKind.VOID,
            ):
                # Try to extract the integer value via the token stream.
                val = self._try_eval_integer_tokens(cursor)
                if val is not None:
                    return Const(name=cursor.spelling, type=prim, value=val)
        return None

    # ── macro extraction ──────────────────────────────────────────────────────

    def _collect_macros(self) -> list[Const]:
        """
        Walk all MACRO_DEFINITION cursors in the TU and build Const nodes for
        simple integer / hex literal #defines.  Multi-token, string, float,
        and function-like macros are silently skipped.

        Call after the main AST walk so callers can append macro Consts after
        struct/enum/function declarations — matching the logical header structure.
        """
        assert self._tu is not None
        out: list[Const] = []
        for cursor in self._tu.cursor.walk_preorder():
            if cursor.kind != cx.CursorKind.MACRO_DEFINITION:
                continue
            # Function-like and expression macros are skipped by _try_parse_macro_literal
            # (requires exactly two tokens: name + one integer literal).
            # Must originate from the primary file
            loc = cursor.location
            if not loc.file or Path(loc.file.name).resolve() != self.header:
                continue

            val, suffix = self._try_parse_macro_literal(cursor)
            if val is None:
                continue

            prim = self._resolver.primitive_for_integer_literal_suffix(suffix)
            out.append(
                Const(
                    name=cursor.spelling,
                    type=prim,
                    value=val,
                )
            )
        return out

    def _try_parse_macro_literal(
        self, cursor: cx.Cursor
    ) -> tuple[int | None, str]:
        """
        Tokenise the macro definition and attempt to parse a single integer
        literal token.

        Returns (value, suffix) on success, (None, "") on failure.

        Token layout for  #define FOO 42u  is:
          tokens[0] = "FOO"  (IDENTIFIER)
          tokens[1] = "42u"  (LITERAL)

        We require exactly 2 tokens (name + one literal).
        """
        tokens = list(cursor.get_tokens())
        if len(tokens) != 2:
            return None, ""
        _name_tok, val_tok = tokens
        if val_tok.kind != cx.TokenKind.LITERAL:
            return None, ""

        raw = val_tok.spelling.strip()
        value, suffix = _match_int_literal(raw)
        if value is None:
            return None, ""
        return value, suffix

    def _try_eval_integer_tokens(self, cursor: cx.Cursor) -> int | None:
        """
        For VAR_DECL cursors: accept only ``= <literal>`` or ``= - <literal>``
        before ``;`` (same integer rules as simple #define macros).
        """
        tokens = list(cursor.get_tokens())
        try:
            eq_i = next(i for i, t in enumerate(tokens) if t.spelling == "=")
        except StopIteration:
            return None
        after_eq = tokens[eq_i + 1 :]
        if after_eq and after_eq[-1].spelling == ";":
            after_eq = after_eq[:-1]
        if len(after_eq) == 1 and after_eq[0].kind == cx.TokenKind.LITERAL:
            val, _ = _match_int_literal(after_eq[0].spelling.strip())
            return val
        if (
            len(after_eq) == 2
            and after_eq[0].spelling == "-"
            and after_eq[1].kind == cx.TokenKind.LITERAL
        ):
            val, _ = _match_int_literal(after_eq[1].spelling.strip())
            if val is None:
                return None
            return -val
        return None
