# src/parser.py
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

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import clang.cindex as cx

from .ir import (
    Array,
    Bitfield,
    BuiltinPrimitiveSpelling,
    Const,
    Decl,
    Enum,
    Enumerant,
    Field,
    Function,
    FunctionPtr,
    Opaque,
    Param,
    Pointer,
    Primitive,
    PrimitiveKind,
    Struct,
    Type,
    Typedef,
    Unit,
)


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
        return f"{self.severity}: {self.file}:{self.line}:{self.col}: {self.message}"


_SEVERITY = {
    cx.Diagnostic.Note:    "note",
    cx.Diagnostic.Warning: "warning",
    cx.Diagnostic.Error:   "error",
    cx.Diagnostic.Fatal:   "fatal",
}


# ─────────────────────────────────────────────────────────────────────────────
#  Primitive type map
#
#  Keys are the canonical clang spelling returned by Type.spelling.
#  Values are BuiltinPrimitiveSpelling; byte width always comes from
#  Type.get_size() in _make_primitive_from_kind (LP64 vs LLP64 `long`, etc.).
# ─────────────────────────────────────────────────────────────────────────────

_PS_VOID = BuiltinPrimitiveSpelling(kind=PrimitiveKind.VOID)
_PS_BOOL = BuiltinPrimitiveSpelling(kind=PrimitiveKind.BOOL)
_PS_CHAR = BuiltinPrimitiveSpelling(kind=PrimitiveKind.CHAR)
_PS_SINT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.INT, is_signed=True)
_PS_UINT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.INT, is_signed=False)
_PS_FLOAT = BuiltinPrimitiveSpelling(kind=PrimitiveKind.FLOAT)

_PRIMITIVE_SPELLINGS: dict[str, BuiltinPrimitiveSpelling] = {
    "void": _PS_VOID,
    "_Bool": _PS_BOOL,
    "char": _PS_CHAR,
    "signed char": _PS_SINT,
    "unsigned char": _PS_UINT,
    "short": _PS_SINT,
    "short int": _PS_SINT,
    "signed short": _PS_SINT,
    "signed short int": _PS_SINT,
    "unsigned short": _PS_UINT,
    "unsigned short int": _PS_UINT,
    "int": _PS_SINT,
    "signed": _PS_SINT,
    "signed int": _PS_SINT,
    "unsigned": _PS_UINT,
    "unsigned int": _PS_UINT,
    "long": _PS_SINT,
    "long int": _PS_SINT,
    "signed long": _PS_SINT,
    "unsigned long": _PS_UINT,
    "unsigned long int": _PS_UINT,
    "long long": _PS_SINT,
    "long long int": _PS_SINT,
    "signed long long": _PS_SINT,
    "signed long long int": _PS_SINT,
    "unsigned long long": _PS_UINT,
    "unsigned long long int": _PS_UINT,
    "float": _PS_FLOAT,
    "double": _PS_FLOAT,
    "long double": _PS_FLOAT,
    # stdint.h typedefs — fast path for spellings clang may emit as builtins
    "int8_t": _PS_SINT,
    "int16_t": _PS_SINT,
    "int32_t": _PS_SINT,
    "int64_t": _PS_SINT,
    "uint8_t": _PS_UINT,
    "uint16_t": _PS_UINT,
    "uint32_t": _PS_UINT,
    "uint64_t": _PS_UINT,
    "size_t": _PS_UINT,
    "ssize_t": _PS_SINT,
    "ptrdiff_t": _PS_SINT,
    "intptr_t": _PS_SINT,
    "uintptr_t": _PS_UINT,
}

# Regex for integer/hex literal macros: optional sign, decimal or 0x…, optional suffix
_INT_LITERAL_RE = re.compile(
    r"^([+-]?\s*)?"
    r"(0[xX][0-9a-fA-F]+|0[0-7]*|[1-9][0-9]*)"
    r"([uUlL]*)$",
)


# ─────────────────────────────────────────────────────────────────────────────
#  ClangParser
# ─────────────────────────────────────────────────────────────────────────────

class ClangParser:
    """
    Parse one C header and produce a Unit.

    Parameters
    ----------
    header:
        Path to the .h file to parse.
    library:
        Logical library name written into Unit (e.g. "zlib").
    link_name:
        Shared-library link name written into Unit (e.g. "z").
    compile_args:
        Extra flags forwarded to libclang (e.g. ["-I/usr/include", "-DFOO=1"]).
    raise_on_error:
        If True (default), raise ParseError when clang reports error/fatal
        diagnostics.  Set to False to collect partial results despite errors.
    """

    def __init__(
        self,
        header: Path | str,
        library: str,
        link_name: str,
        compile_args: list[str] | None = None,
        raise_on_error: bool = True,
    ) -> None:
        self.header = Path(header).resolve()
        self.library = library
        self.link_name = link_name
        self.compile_args = list(compile_args or [])
        self.raise_on_error = raise_on_error

        # diagnostics collected during the run
        self.diagnostics: list[FrontendDiagnostic] = []

        # internal state built while walking the AST
        # maps C cursor usr (Unified Symbol Resolution) → already-built Type
        # used to handle recursive/self-referential struct types
        self._type_cache: dict[str, Type] = {}

        # set of struct/union C names that are fully defined (have a body)
        # used to distinguish Struct from Opaque
        self._defined_structs: set[str] = set()

        # Unit accumulator
        self._decls: list[Decl] = []

        # parse
        self._tu = self._parse()

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
            if decl is not None:
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
        Recursively walk the entire TU and record every struct/union cursor
        that has a definition (is_definition() == True).  Run before the main
        walk so that forward-declared names can be identified as opaque.
        """
        for cursor in root.walk_preorder():
            if cursor.kind in (
                cx.CursorKind.STRUCT_DECL,
                cx.CursorKind.UNION_DECL,
            ) and cursor.is_definition():
                # cursor.spelling is "" for anonymous structs — skip those
                if cursor.spelling:
                    self._defined_structs.add(cursor.spelling)

    # ── top-level dispatch ────────────────────────────────────────────────────

    def _visit_top_level(self, cursor: cx.Cursor) -> Decl | None:
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
                return self._build_struct(cursor)
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
        ret_ir = self._resolve_type(fn_type.get_result())

        # Parameters — iterate child cursors of kind PARM_DECL
        params: list[Param] = []
        for child in cursor.get_children():
            if child.kind == cx.CursorKind.PARM_DECL:
                param_type = self._resolve_type(child.type)
                params.append(Param(name=child.spelling, type=param_type))

        is_variadic = fn_type.kind == cx.TypeKind.FUNCTIONNOPROTO or (
            # FunctionProto with ellipsis
            fn_type.kind == cx.TypeKind.FUNCTIONPROTO
            and fn_type.is_function_variadic()
        )

        return Function(
            name=cursor.spelling,
            link_name=cursor.spelling,
            ret=ret_ir,
            params=params,
            is_variadic=is_variadic,
        )

    # ── struct / union ────────────────────────────────────────────────────────

    def _build_struct(self, cursor: cx.Cursor) -> Struct | None:
        """
        STRUCT_DECL or UNION_DECL cursor (definition) → Struct.

        Layout is taken from clang's type layout queries — never computed
        by hand.  Bitfield members get Bitfield; anonymous bitfield padding
        is kept with name="" so the emitter can collapse the struct to _bits.
        """
        c_name = cursor.spelling
        clang_type = cursor.type

        # Guard against libclang returning -1 / -2 for incomplete types.
        # (Shouldn't happen because we only call this for definitions, but
        # be defensive.)
        size_raw = clang_type.get_size()
        align_raw = clang_type.get_align()
        size_bytes = max(0, size_raw) if size_raw > 0 else 0
        align_bytes = max(1, align_raw) if align_raw > 0 else 1

        fields: list[Field] = []
        for child in cursor.get_children():
            if child.kind != cx.CursorKind.FIELD_DECL:
                continue

            field_name = child.spelling  # "" for anonymous bitfield padding

            # byte_offset: clang gives us bit offset via get_field_offset_of
            # (or Type.get_offset in newer libclang).
            bit_off_result = clang_type.get_offset(field_name) if field_name else -1
            byte_offset = bit_off_result // 8 if bit_off_result >= 0 else 0

            if child.is_bitfield():
                backing = self._resolve_type(child.type)
                # backing must be an integer primitive
                if not isinstance(backing, Primitive):
                    # Unexpected — skip silently
                    continue
                bw = child.get_bitfield_width()
                # bit_offset within the backing storage word
                bit_off = bit_off_result if bit_off_result >= 0 else 0
                field_type: Type = Bitfield(
                    backing_type=backing,
                    bit_offset=bit_off,
                    bit_width=bw,
                )
            else:
                field_type = self._resolve_type(child.type)

            fields.append(Field(
                name=field_name,
                type=field_type,
                byte_offset=byte_offset,
            ))

        is_union = (cursor.kind == cx.CursorKind.UNION_DECL)

        struct = Struct(
            name=c_name,
            c_name=c_name,
            fields=fields,
            size_bytes=size_bytes,
            align_bytes=align_bytes,
            is_union=is_union,
        )

        # Cache under the cursor's USR so recursive references can find it.
        self._type_cache[cursor.get_usr()] = struct
        return struct

    # ── enum ──────────────────────────────────────────────────────────────────

    def _build_enum(self, cursor: cx.Cursor) -> Enum | None:
        """
        ENUM_DECL cursor (definition) → Enum.

        The underlying integer type comes from clang's enum_type property
        on the cursor (new enough libclang) or falls back to the canonical
        type of the first enumerant.
        """
        c_name = cursor.spelling
        # Underlying integer type: use cursor.enum_type if available
        underlying_clang = cursor.enum_type
        underlying = self._resolve_primitive(underlying_clang)
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

        # Anonymous enum (c_name == "") — return None here; the caller
        # (_visit_top_level / _collect_macros path) will harvest the
        # enumerants as individual Const nodes instead.
        if not c_name:
            for e in enumerants:
                self._decls.append(Const(
                    name=e.name,
                    type=underlying,
                    value=e.value,
                ))
            return None

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
        aliased = self._resolve_type(cursor.underlying_typedef_type)
        return Typedef(name=name, aliased=aliased)

    # ── top-level const variable ───────────────────────────────────────────────

    def _build_var_const(self, cursor: cx.Cursor) -> Const | None:
        """
        Top-level VAR_DECL with a constant initialiser → Const.
        Only integer types are supported; anything else is skipped.
        """
        if cursor.type.is_const_qualified():
            prim = self._resolve_primitive(cursor.type)
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

            # Infer signedness from the suffix
            is_signed = "u" not in suffix.lower()
            # Size: default to 4 (int); upgrade to 8 if "ll" in suffix
            size = 8 if "ll" in suffix.lower() else 4
            prim = Primitive(
                name="unsigned int" if not is_signed else "int",
                kind=PrimitiveKind.INT,
                is_signed=is_signed,
                size_bytes=size,
            )
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
        m = _INT_LITERAL_RE.match(raw)
        if not m:
            return None, ""

        sign_str = (m.group(1) or "").strip()
        num_str = m.group(2)
        suffix = m.group(3) or ""

        try:
            value = int(num_str, 0)
        except ValueError:
            return None, ""

        if sign_str == "-":
            value = -value

        return value, suffix

    def _try_eval_integer_tokens(self, cursor: cx.Cursor) -> int | None:
        """
        For VAR_DECL cursors: scan tokens for the last integer literal.
        e.g.  const int X = 7;  → tokens[-2] is "7".
        """
        tokens = list(cursor.get_tokens())
        for tok in reversed(tokens):
            if tok.kind == cx.TokenKind.LITERAL:
                raw = tok.spelling.strip().rstrip("uUlL")
                try:
                    return int(raw, 0)
                except ValueError:
                    return None
        return None

    # ── type resolution ───────────────────────────────────────────────────────

    def _resolve_type(self, clang_type: cx.Type) -> Type:
        """
        Convert a clang Type to a Type, recursively.

        This is the central type-mapping function.  It handles:
          - Qualifiers (const) — stripped but is_const is propagated to Pointer
          - Typedefs — the canonical type is used so chains are collapsed
          - Pointers and arrays
          - Function prototypes (produces FunctionPtr)
          - Struct/union/enum references
          - Elaborated types (the "struct Foo" in "struct Foo *")
        """
        tk = clang_type.kind

        # ── qualifiers / sugar ────────────────────────────────────────────
        # CXType_Elaborated wraps "struct Foo", "enum Bar" — unwrap it.
        if tk == cx.TypeKind.ELABORATED:
            return self._resolve_type(clang_type.get_named_type())

        # Typedef — resolve via canonical type so chains collapse.
        # We still need to detect when the typedef refers to a struct/enum
        # that we have an IRType for in the cache, so try canonical first.
        if tk == cx.TypeKind.TYPEDEF:
            return self._resolve_type(clang_type.get_canonical())

        # ── void ──────────────────────────────────────────────────────────
        if tk == cx.TypeKind.VOID:
            return Primitive(
                "void",
                kind=PrimitiveKind.VOID,
                is_signed=False,
                size_bytes=0,
            )

        # ── bool ──────────────────────────────────────────────────────────
        if tk == cx.TypeKind.BOOL:
            return Primitive(
                "_Bool",
                kind=PrimitiveKind.BOOL,
                is_signed=False,
                size_bytes=1,
            )

        # ── integer primitives ────────────────────────────────────────────
        if tk in (
            cx.TypeKind.CHAR_U, cx.TypeKind.UCHAR,
            cx.TypeKind.CHAR16, cx.TypeKind.CHAR32,
            cx.TypeKind.USHORT, cx.TypeKind.UINT,
            cx.TypeKind.ULONG, cx.TypeKind.ULONGLONG, cx.TypeKind.UINT128,
            cx.TypeKind.CHAR_S, cx.TypeKind.SCHAR,
            cx.TypeKind.WCHAR,
            cx.TypeKind.SHORT, cx.TypeKind.INT,
            cx.TypeKind.LONG, cx.TypeKind.LONGLONG, cx.TypeKind.INT128,
        ):
            return self._make_primitive_from_kind(clang_type)

        # ── float primitives (including _Float16). 128-bit floats (__float128,
        # __ibm128) have no Mojo analogue — handled below as Opaque.
        if tk in (
            cx.TypeKind.FLOAT,
            cx.TypeKind.DOUBLE,
            cx.TypeKind.LONGDOUBLE,
            cx.TypeKind.HALF,
        ):
            return self._make_primitive_from_kind(clang_type)

        # ── pointer ───────────────────────────────────────────────────────
        if tk == cx.TypeKind.POINTER:
            pointee_clang = clang_type.get_pointee()
            is_const = pointee_clang.is_const_qualified()

            # void* → Pointer(pointee=None)
            if pointee_clang.kind == cx.TypeKind.VOID:
                return Pointer(pointee=None, is_const=False)

            # Function pointer: ret (*)(args)
            canonical_pointee = pointee_clang.get_canonical()
            if canonical_pointee.kind in (
                cx.TypeKind.FUNCTIONPROTO,
                cx.TypeKind.FUNCTIONNOPROTO,
            ):
                return self._resolve_function_ptr(canonical_pointee)

            pointee_ir = self._resolve_type(pointee_clang)
            return Pointer(pointee=pointee_ir, is_const=is_const)

        # ── fixed-size array ──────────────────────────────────────────────
        if tk == cx.TypeKind.CONSTANTARRAY:
            element_ir = self._resolve_type(clang_type.get_array_element_type())
            size = clang_type.get_array_size()
            return Array(element=element_ir, size=size)

        # ── incomplete / variable-length array — treat as pointer ─────────
        if tk in (
            cx.TypeKind.INCOMPLETEARRAY,
            cx.TypeKind.VARIABLEARRAY,
            cx.TypeKind.DEPENDENTSIZEDARRAY,
        ):
            element_ir = self._resolve_type(clang_type.get_array_element_type())
            return Array(element=element_ir, size=None)

        # ── struct / union ────────────────────────────────────────────────
        if tk in (cx.TypeKind.RECORD,):
            return self._resolve_record(clang_type)

        # ── enum ──────────────────────────────────────────────────────────
        if tk == cx.TypeKind.ENUM:
            decl_cursor = clang_type.get_declaration()
            c_name = decl_cursor.spelling
            # Return a reference primitive matching the enum's underlying type.
            # The full Enum is emitted separately; here we just need the type.
            underlying_clang = decl_cursor.enum_type
            prim = self._resolve_primitive(underlying_clang)
            if prim:
                return prim
            return Primitive(
                "unsigned int",
                kind=PrimitiveKind.INT,
                is_signed=False,
                size_bytes=4,
            )

        # ── function prototype (not through pointer) ───────────────────────
        if tk in (cx.TypeKind.FUNCTIONPROTO, cx.TypeKind.FUNCTIONNOPROTO):
            return self._resolve_function_ptr(clang_type)

        # ── anything we don't recognise → opaque (e.g. COMPLEX, __float128,
        # __ibm128, vectors) ───────────────────────────────────────────────
        spelling = clang_type.spelling or "unknown"
        return Opaque(name=spelling)

    def _resolve_record(self, clang_type: cx.Type) -> Type:
        """
        Struct or union type → either a cached Struct or Opaque.

        If the struct definition has been seen (is in _defined_structs) and
        the cursor USR is in _type_cache, return the cached Struct.
        If the definition hasn't been seen, return Opaque so the emitter
        can write  alias Foo = OpaquePointer.
        """
        decl_cursor = clang_type.get_declaration()
        c_name = decl_cursor.spelling

        # Try the USR cache first (handles recursive structs)
        usr = decl_cursor.get_usr()
        if usr in self._type_cache:
            return self._type_cache[usr]

        if c_name and c_name in self._defined_structs:
            # The definition exists in this TU but we haven't built the
            # Struct yet (possible with forward-reference ordering).
            # Build it now and cache to avoid infinite recursion.
            struct = self._build_struct(decl_cursor.get_definition())
            if struct is not None:
                self._type_cache[usr] = struct
                return struct

        # No definition — opaque handle
        return Opaque(name=c_name or clang_type.spelling)

    def _resolve_function_ptr(self, fn_type: cx.Type) -> FunctionPtr:
        """
        FunctionProto or FunctionNoProto → FunctionPtr.
        """
        ret_ir = self._resolve_type(fn_type.get_result())
        params: list[Type] = []
        if fn_type.kind == cx.TypeKind.FUNCTIONPROTO:
            for arg_t in fn_type.argument_types():
                params.append(self._resolve_type(arg_t))
            is_variadic = fn_type.is_function_variadic()
        else:
            is_variadic = False
        return FunctionPtr(ret=ret_ir, params=params, is_variadic=is_variadic)

    def _make_primitive_from_kind(self, clang_type: cx.Type) -> Primitive:
        """
        Build Primitive for a scalar numeric type.  Uses clang's spelling
        (which is the canonical C name) and get_size() for the actual byte
        width so we are correct on all target triples.
        """
        canonical = clang_type.get_canonical()
        spelling = canonical.spelling  # e.g. "unsigned long int"

        # Normalise spelling: strip "const", "volatile", "restrict"
        norm = re.sub(r"\b(const|volatile|restrict)\b", "", spelling).strip()

        defaults = _PRIMITIVE_SPELLINGS.get(norm)
        if defaults:
            kind = defaults.kind
            if kind == PrimitiveKind.INT:
                is_signed = defaults.is_signed
            elif kind == PrimitiveKind.CHAR:
                is_signed = canonical.kind == cx.TypeKind.CHAR_S
            else:
                is_signed = False
        else:
            # Unknown spelling — guess from TypeKind
            tk = canonical.kind
            if tk == cx.TypeKind.BOOL:
                kind = PrimitiveKind.BOOL
                is_signed = False
            elif tk in (
                cx.TypeKind.FLOAT,
                cx.TypeKind.DOUBLE,
                cx.TypeKind.LONGDOUBLE,
                cx.TypeKind.HALF,
            ):
                kind = PrimitiveKind.FLOAT
                is_signed = False
            elif tk in (cx.TypeKind.CHAR_S, cx.TypeKind.CHAR_U) and norm == "char":
                kind = PrimitiveKind.CHAR
                is_signed = tk == cx.TypeKind.CHAR_S
            else:
                kind = PrimitiveKind.INT
                is_signed = tk in (
                    cx.TypeKind.CHAR_S,
                    cx.TypeKind.SCHAR,
                    cx.TypeKind.SHORT,
                    cx.TypeKind.INT,
                    cx.TypeKind.LONG,
                    cx.TypeKind.LONGLONG,
                    cx.TypeKind.INT128,
                    cx.TypeKind.WCHAR,
                )

        # Always ask clang for the actual size — overrides our table default.
        size_raw = canonical.get_size()
        size_bytes = size_raw if size_raw > 0 else 0

        return Primitive(
            name=norm or spelling,
            kind=kind,
            is_signed=is_signed,
            size_bytes=size_bytes,
        )

    def _resolve_primitive(self, clang_type: cx.Type) -> Primitive | None:
        """
        Attempt to resolve clang_type to a Primitive.
        Returns None if the type is not a primitive scalar.
        """
        canonical = clang_type.get_canonical()
        tk = canonical.kind
        scalar_kinds = {
            cx.TypeKind.BOOL,
            cx.TypeKind.CHAR_U, cx.TypeKind.UCHAR,
            cx.TypeKind.CHAR16, cx.TypeKind.CHAR32,
            cx.TypeKind.USHORT, cx.TypeKind.UINT,
            cx.TypeKind.ULONG, cx.TypeKind.ULONGLONG,
            cx.TypeKind.UINT128,
            cx.TypeKind.CHAR_S, cx.TypeKind.SCHAR,
            cx.TypeKind.WCHAR,
            cx.TypeKind.SHORT, cx.TypeKind.INT,
            cx.TypeKind.LONG, cx.TypeKind.LONGLONG,
            cx.TypeKind.INT128,
            cx.TypeKind.FLOAT,
            cx.TypeKind.DOUBLE,
            cx.TypeKind.LONGDOUBLE,
            cx.TypeKind.HALF,
        }
        if tk not in scalar_kinds:
            return None
        return self._make_primitive_from_kind(clang_type)
