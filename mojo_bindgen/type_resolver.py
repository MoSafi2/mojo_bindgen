# mojo_bindgen/type_resolver.py
"""Clang type → IR :class:`Type` resolution (used by :class:`~mojo_bindgen.parser.ClangParser`)."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass

import clang.cindex as cx

from mojo_bindgen.ir import (
    Array,
    FunctionPtr,
    Opaque,
    Pointer,
    Primitive,
    PrimitiveKind,
    Struct,
    StructRef,
    Type,
    TypeRef,
)


# ─────────────────────────────────────────────────────────────────────────────
#  Primitive type map
#
#  Keys are the canonical clang spelling returned by Type.spelling.
#  Values are BuiltinPrimitiveSpelling; byte width always comes from
#  Type.get_size() in make_primitive_from_kind (LP64 vs LLP64 `long`, etc.).
# ─────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BuiltinPrimitiveSpelling:
    """Kind (and for INT, signedness) for a canonical C/clang type spelling."""

    kind: PrimitiveKind
    is_signed: bool = False  # only used when kind is INT; ignored for CHAR (from clang)


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


# Suffixes pre-warmed so typical #define literals avoid lazy probe parses.
_LITERAL_SUFFIX_PREWARM: frozenset[str] = frozenset(
    {
        "",
        "u",
        "U",
        "l",
        "L",
        "ll",
        "LL",
        "ul",
        "uL",
        "Ul",
        "UL",
        "lu",
        "lU",
        "Lu",
        "LU",
        "llu",
        "llU",
        "LLu",
        "LLU",
        "ull",
        "uLL",
        "Ull",
        "ULL",
    }
)


class TypeResolver:
    """
    Maps libclang :class:`clang.cindex.Type` values to IR :class:`~mojo_bindgen.ir.Type` nodes.

    Caches struct layouts under cursor USR; ``defined_structs`` is filled by the
    parser's first pass over the translation unit.

    The ``build_struct`` callback is supplied by :class:`~mojo_bindgen.parser.ClangParser`
    and may call back into the parser to materialize nested anonymous structs — a
    deliberate cycle for layout fidelity.
    """

    def __init__(
        self,
        *,
        compile_args: list[str],
        append_type_kind_warning: Callable[[cx.Type, str], None],
        build_struct: Callable[[cx.Cursor, list[Struct] | None], Struct | None],
    ) -> None:
        self.compile_args = compile_args
        self._append_type_kind_warning = append_type_kind_warning
        self._build_struct = build_struct
        self.type_cache: dict[str, Struct] = {}
        self.defined_structs: set[str] = set()
        self._literal_suffix_cache: dict[str, Primitive] = {}
        for suf in _LITERAL_SUFFIX_PREWARM:
            self.primitive_for_integer_literal_suffix(suf)

    def primitive_for_integer_literal_suffix(self, suffix: str) -> Primitive:
        """
        Map a C integer literal suffix (``u``, ``ul``, ``ull``, …) to an IR
        :class:`~mojo_bindgen.ir.Primitive` using the same ABI as ``compile_args``
        (LP64, LLP64, …). Results are memoized per suffix.
        """
        if suffix in self._literal_suffix_cache:
            return self._literal_suffix_cache[suffix]
        spell = _c_integer_spelling_for_literal_suffix(suffix)
        idx = cx.Index.create()
        src = f"{spell} __bindgen_m;\n"
        tu = idx.parse(
            "__bindgen_suffix_probe.c",
            args=["-x", "c", "-std=c11"] + self.compile_args,
            unsaved_files=[("__bindgen_suffix_probe.c", src)],
            options=cx.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES,
        )
        prim: Primitive | None = None
        for c in tu.cursor.get_children():
            if c.kind == cx.CursorKind.VAR_DECL and c.spelling == "__bindgen_m":
                prim = self.make_primitive_from_kind(c.type)
                break
        if prim is None:
            prim = Primitive(
                name=spell,
                kind=PrimitiveKind.INT,
                is_signed="unsigned" not in spell.split(),
                size_bytes=4,
            )
        self._literal_suffix_cache[suffix] = prim
        return prim

    def resolve(self, clang_type: cx.Type) -> Type:
        """
        Convert a clang Type to a Type, recursively.

        Handles qualifiers, typedef chains, pointers, arrays, function types,
        struct/union/enum references, and elaborated types.
        """
        tk = clang_type.kind

        if tk == cx.TypeKind.INVALID:
            self._append_type_kind_warning(clang_type, "invalid type (INVALID)")
            return Opaque(name="invalid")
        if tk == cx.TypeKind.UNEXPOSED:
            self._append_type_kind_warning(clang_type, "unexposed type (UNEXPOSED)")
            return Opaque(name=clang_type.spelling or "unexposed")

        if tk == cx.TypeKind.ELABORATED:
            return self.resolve(clang_type.get_named_type())

        if tk == cx.TypeKind.TYPEDEF:
            decl = clang_type.get_declaration()
            alias = decl.spelling or clang_type.spelling or ""
            return TypeRef(
                name=alias,
                canonical=self.resolve(clang_type.get_canonical()),
            )

        if tk == cx.TypeKind.VOID:
            return Primitive(
                "void",
                kind=PrimitiveKind.VOID,
                is_signed=False,
                size_bytes=0,
            )

        if tk == cx.TypeKind.BOOL:
            return Primitive(
                "_Bool",
                kind=PrimitiveKind.BOOL,
                is_signed=False,
                size_bytes=1,
            )

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
            return self.make_primitive_from_kind(clang_type)

        if tk in (
            cx.TypeKind.FLOAT,
            cx.TypeKind.DOUBLE,
            cx.TypeKind.LONGDOUBLE,
            cx.TypeKind.HALF,
        ):
            return self.make_primitive_from_kind(clang_type)

        if tk == cx.TypeKind.POINTER:
            pointee_clang = clang_type.get_pointee()
            is_const = pointee_clang.is_const_qualified()

            if pointee_clang.kind == cx.TypeKind.VOID:
                return Pointer(pointee=None, is_const=is_const)

            canonical_pointee = pointee_clang.get_canonical()
            if canonical_pointee.kind in (
                cx.TypeKind.FUNCTIONPROTO,
                cx.TypeKind.FUNCTIONNOPROTO,
            ):
                return self._resolve_function_ptr(canonical_pointee)

            pointee_ir = self.resolve(pointee_clang)
            return Pointer(pointee=pointee_ir, is_const=is_const)

        if tk == cx.TypeKind.CONSTANTARRAY:
            element_ir = self.resolve(clang_type.get_array_element_type())
            size = clang_type.get_array_size()
            return Array(element=element_ir, size=size)

        if tk in (
            cx.TypeKind.INCOMPLETEARRAY,
            cx.TypeKind.VARIABLEARRAY,
            cx.TypeKind.DEPENDENTSIZEDARRAY,
        ):
            element_ir = self.resolve(clang_type.get_array_element_type())
            return Array(element=element_ir, size=None)

        if tk in (cx.TypeKind.RECORD,):
            return self._resolve_record(clang_type)

        if tk == cx.TypeKind.ENUM:
            decl_cursor = clang_type.get_declaration()
            underlying_clang = decl_cursor.enum_type
            prim = self.resolve_primitive(underlying_clang)
            if prim:
                return prim
            return Primitive(
                "unsigned int",
                kind=PrimitiveKind.INT,
                is_signed=False,
                size_bytes=4,
            )

        if tk in (cx.TypeKind.FUNCTIONPROTO, cx.TypeKind.FUNCTIONNOPROTO):
            return self._resolve_function_ptr(clang_type)

        spelling = clang_type.spelling or "unknown"
        return Opaque(name=spelling)

    def _resolve_record(self, clang_type: cx.Type) -> Type:
        """
        Struct or union type → :class:`StructRef`, or :class:`Opaque` if incomplete.
        """
        decl_cursor = clang_type.get_declaration()
        c_name = decl_cursor.spelling

        usr = decl_cursor.get_usr()
        if usr in self.type_cache:
            s = self.type_cache[usr]
            return StructRef(
                name=s.name,
                c_name=s.c_name,
                is_union=s.is_union,
                size_bytes=s.size_bytes,
            )

        if c_name and c_name in self.defined_structs:
            struct = self._build_struct(decl_cursor.get_definition(), None)
            if struct is not None:
                self.type_cache[usr] = struct
                return StructRef(
                    name=struct.name,
                    c_name=struct.c_name,
                    is_union=struct.is_union,
                    size_bytes=struct.size_bytes,
                )

        if not c_name:
            digest = hashlib.sha256(usr.encode("utf-8")).hexdigest()[:16]
            return Opaque(name=f"__bindgen_anon_{digest}")
        return Opaque(name=c_name)

    def _resolve_function_ptr(self, fn_type: cx.Type) -> FunctionPtr:
        ret_ir = self.resolve(fn_type.get_result())
        params: list[Type] = []
        if fn_type.kind == cx.TypeKind.FUNCTIONPROTO:
            for arg_t in fn_type.argument_types():
                params.append(self.resolve(arg_t))
            is_variadic = fn_type.is_function_variadic()
        else:
            is_variadic = False
        return FunctionPtr(ret=ret_ir, params=params, is_variadic=is_variadic)

    def make_primitive_from_kind(self, clang_type: cx.Type) -> Primitive:
        canonical = clang_type.get_canonical()
        spelling = canonical.spelling

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

        size_raw = canonical.get_size()
        size_bytes = size_raw if size_raw > 0 else 0

        return Primitive(
            name=norm or spelling,
            kind=kind,
            is_signed=is_signed,
            size_bytes=size_bytes,
        )

    def resolve_primitive(self, clang_type: cx.Type) -> Primitive | None:
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
        return self.make_primitive_from_kind(clang_type)
