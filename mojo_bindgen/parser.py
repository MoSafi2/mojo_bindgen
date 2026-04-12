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

import hashlib
import os
import re
import subprocess
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import clang.cindex as cx

from mojo_bindgen.ir import (
    Const,
    Decl,
    Enum,
    Enumerant,
    Field,
    Function,
    Param,
    Primitive,
    PrimitiveKind,
    Struct,
    StructRef,
    Type,
    Typedef,
    Unit,
)
from mojo_bindgen.type_resolver import TypeResolver


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


def _c_integer_spelling_for_literal_suffix(suffix: str) -> str:
    """Map a C integer literal suffix (e.g. ``ul``, ``ULL``) to a type spelling."""
    if not suffix:
        return "int"
    s = suffix.lower()
    has_u = "u" in s
    l_count = s.count("l")
    if l_count >= 2:
        return "unsigned long long" if has_u else "long long"
    if l_count == 1:
        return "unsigned long" if has_u else "long"
    return "unsigned int" if has_u else "int"


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


# Directory containing this package (`mojo_bindgen/`).  Parent is the repository root.
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _resolve_header_path(header: Path | str) -> Path:
    """
    Resolve a header path for parsing.

    Absolute paths must exist as files.

    Relative paths are resolved against the **current working directory** first.
    If the environment variable ``MOJO_BINDGEN_DEV`` is set to ``"1"``, the
    repository root (parent of ``mojo_bindgen/``) is also tried so paths like
    ``tests/fixtures/foo.h`` work when the cwd is the repo root or ``mojo_bindgen/``.  Installed packages
    should not rely on this; use absolute paths or run with an appropriate cwd.
    """
    p = Path(header)
    if p.is_absolute():
        r = p.resolve()
        if not r.is_file():
            raise FileNotFoundError(f"header not found: {header}")
        return r

    cwd_resolved = (Path.cwd() / p).resolve()
    candidates: list[Path] = [cwd_resolved]
    dev_repo = os.environ.get("MOJO_BINDGEN_DEV") == "1"
    if dev_repo:
        candidates.append((_REPO_ROOT / p).resolve())
    for c in candidates:
        if c.is_file():
            return c
    tried = ", ".join(str(c) for c in candidates)
    hint = ""
    if not dev_repo and (_REPO_ROOT / p).resolve().is_file():
        hint = (
            " A matching file exists under the package repository root; set "
            "MOJO_BINDGEN_DEV=1 to allow resolving relative paths against it, "
            "or use an absolute path."
        )
    raise FileNotFoundError(
        f"header not found: {header!r} (tried {tried}).{hint}"
    )


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

    Parameters
    ----------
    header:
        Path to the ``.h`` file. Absolute paths must exist. Relative paths are
        resolved against the **current working directory** only unless
        ``MOJO_BINDGEN_DEV=1`` is set, in which case the repository root (parent
        of ``mojo_bindgen/``) is also tried—useful for local development; installed
        packages should pass absolute paths or set cwd appropriately.
    library:
        Logical library name written into Unit (e.g. ``"zlib"``).
    link_name:
        Shared-library link name written into Unit (e.g. ``"z"``).
    compile_args:
        Flags forwarded to libclang **in addition** to ``-x c -std=c11`` (and
        the primary file). If ``None`` (default), :func:`_default_system_compile_args`
        supplies typical ``-I`` paths (``/usr/include`` plus a probe from ``cc`` /
        ``clang``). For cross-compilation, NixOS, or non-default sysroots, pass
        explicit ``-I``, ``-isystem``, ``--sysroot``, and target triple flags
        here so ``#include <stdint.h>`` and system headers resolve. Pass ``[]``
        to disable the default system includes (only the bare parse flags apply).
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

        # parse
        self._tu = self._parse()

        self._resolver = TypeResolver(
            compile_args=self.compile_args,
            append_type_kind_warning=self._append_type_kind_warning,
            build_struct=self._build_struct,
        )

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

    # ── public entry point ────────────────────────────────────────────────────

    def run(self) -> Unit:
        """
        Walk the translation unit and return the populated Unit.
        Call once per ClangParser instance.
        """
        # First pass: collect all struct/union definitions so we know which
        # names are opaque vs fully defined before we process any fields.
        self._collect_defined_structs(self._tu.cursor)

        # Second pass: emit IR declarations in source order.
        for cursor in self._primary_cursors():
            decl = self._visit_top_level(cursor)
            if decl is None:
                continue
            if isinstance(decl, list):
                self._decls.extend(decl)
            else:
                self._decls.append(decl)

        # Third pass: extract integer #define macros.
        self._collect_macros()

        return Unit(
            source_header=str(self.header),
            library=self.library,
            link_name=self.link_name,
            decls=self._decls,
        )

    # ── parsing ───────────────────────────────────────────────────────────────

    def _parse(self) -> cx.TranslationUnit:
        index = cx.Index.create()
        args = ["-x", "c", "-std=c11"] + self.compile_args
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
            if cursor.is_definition():
                return self._build_enum(cursor)
            return None

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
        ret_ir = self._resolver.resolve(fn_type.get_result())

        # Parameters — iterate child cursors of kind PARM_DECL
        params: list[Param] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PARM_DECL:
                param_type = self._resolver.resolve(child.type)
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
            name=cursor.spelling,
            link_name=cursor.spelling,
            ret=ret_ir,
            params=params,
            is_variadic=is_variadic,
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
        c_name_raw = cursor.spelling
        if not c_name_raw:
            usr0 = cursor.get_usr()
            digest = hashlib.sha256(usr0.encode("utf-8")).hexdigest()[:16]
            synth = f"__bindgen_anon_{digest}"
            c_name = synth
            name = synth
        else:
            c_name = c_name_raw
            name = c_name

        clang_type = cursor.type

        size_raw = clang_type.get_size()
        align_raw = clang_type.get_align()
        size_bytes = max(0, size_raw) if size_raw > 0 else 0
        align_bytes = max(1, align_raw) if align_raw > 0 else 1

        fields: list[Field] = []
        for child in cursor.get_children():
            if child.kind != cx.CursorKind.FIELD_DECL:
                continue

            field_name = child.spelling  # "" for anonymous bitfield padding

            bit_off_result = clang_type.get_offset(field_name) if field_name else -1
            byte_offset = bit_off_result // 8 if bit_off_result >= 0 else 0

            if child.is_bitfield():
                backing = self._resolver.resolve(child.type)
                if not isinstance(backing, Primitive):
                    continue
                bw = child.get_bitfield_width()
                bit_off = bit_off_result if bit_off_result >= 0 else 0
                fields.append(
                    Field(
                        name=field_name,
                        type=backing,
                        byte_offset=byte_offset,
                        is_bitfield=True,
                        bit_offset=bit_off,
                        bit_width=bw,
                    )
                )
                continue

            ft = child.type.get_canonical()
            if ft.kind == cx.TypeKind.RECORD:
                decl = ft.get_declaration()
                def_c = decl.get_definition()
                if (
                    def_c is not None
                    and not decl.spelling
                    and def_c.kind
                    in (cx.CursorKind.STRUCT_DECL, cx.CursorKind.UNION_DECL)
                ):
                    inner = self._build_struct(def_c, nested_out)
                    if inner is not None:
                        field_type: Type = StructRef(
                            name=inner.name,
                            c_name=inner.c_name,
                            is_union=inner.is_union,
                            size_bytes=inner.size_bytes,
                        )
                    else:
                        field_type = self._resolver.resolve(child.type)
                else:
                    field_type = self._resolver.resolve(child.type)
            else:
                field_type = self._resolver.resolve(child.type)

            fields.append(
                Field(
                    name=field_name,
                    type=field_type,
                    byte_offset=byte_offset,
                )
            )

        is_union = cursor.kind == cx.CursorKind.UNION_DECL

        struct = Struct(
            name=name,
            c_name=c_name,
            fields=fields,
            size_bytes=size_bytes,
            align_bytes=align_bytes,
            is_union=is_union,
        )

        self._resolver.type_cache[cursor.get_usr()] = struct
        if nested_out is not None and not c_name_raw:
            nested_out.append(struct)
        return struct

    # ── enum ──────────────────────────────────────────────────────────────────

    def _build_enum(self, cursor: cx.Cursor) -> Enum | list[Const] | None:
        """
        ENUM_DECL cursor (definition) → Enum.

        The underlying integer type comes from clang's enum_type property
        on the cursor (new enough libclang) or falls back to the canonical
        type of the first enumerant.
        """
        c_name = cursor.spelling
        # Underlying integer type: use cursor.enum_type if available
        underlying_clang = cursor.enum_type
        underlying = self._resolver.resolve_primitive(underlying_clang)
        if underlying is None:
            # Fallback: treat as unsigned int
            underlying = Primitive(
                "unsigned int",
                kind=PrimitiveKind.INT,
                is_signed=False,
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

        # Anonymous enum (c_name == "") — enumerants become top-level Const nodes.
        if not c_name:
            return [
                Const(name=e.name, type=underlying, value=e.value)
                for e in enumerants
            ]

        return Enum(
            name=c_name,
            c_name=c_name,
            underlying=underlying,
            enumerants=enumerants,
        )

    # ── typedef ───────────────────────────────────────────────────────────────

    def _build_typedef(self, cursor: cx.Cursor) -> Typedef | None:
        """
        TYPEDEF_DECL cursor → Typedef.

        The underlying type is resolved by walking through the typedef chain
        until we hit a non-typedef type (struct, primitive, pointer, etc.).
        """
        name = cursor.spelling
        # cursor.underlying_typedef_type gives us the *direct* aliased type,
        # not the fully canonical one.  We resolve it ourselves so the IR
        # always contains the base type — the TypeResolver pass still runs
        # afterwards for cross-TU resolution, but simple same-TU chains are
        # collapsed here.
        aliased = self._resolver.resolve(cursor.underlying_typedef_type)
        return Typedef(name=name, aliased=aliased)

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

    def _collect_macros(self) -> None:
        """
        Walk all MACRO_DEFINITION cursors in the TU and emit Const for
        simple integer / hex literal #defines.  Multi-token, string, float,
        and function-like macros are silently skipped.

        This runs after the main AST walk so that macro Consts are appended
        after struct/enum/function declarations in the output — matching the
        logical header structure.
        """
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

            prim = self._primitive_for_integer_literal_suffix(suffix)
            self._decls.append(Const(
                name=cursor.spelling,
                type=prim,
                value=val,
            ))

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

    def _primitive_for_integer_literal_suffix(self, suffix: str) -> Primitive:
        """
        Build a Primitive matching the C type of an integer literal suffix
        (``u``, ``ul``, ``ull``, …) using the same ABI as this parse (LP64, …).
        """
        spell = _c_integer_spelling_for_literal_suffix(suffix)
        idx = cx.Index.create()
        src = f"{spell} __bindgen_m;\n"
        tu = idx.parse(
            "__bindgen_suffix_probe.c",
            args=["-x", "c", "-std=c11"] + self.compile_args,
            unsaved_files=[("__bindgen_suffix_probe.c", src)],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        for c in tu.cursor.get_children():
            if c.kind == cx.CursorKind.VAR_DECL and c.spelling == "__bindgen_m":
                return self._resolver.make_primitive_from_kind(c.type)
        return Primitive(
            name=spell,
            kind=PrimitiveKind.INT,
            is_signed="unsigned" not in spell.split(),
            size_bytes=4,
        )
